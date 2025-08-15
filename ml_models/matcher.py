import re
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from dataclasses import dataclass
from difflib import SequenceMatcher

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class MatchResult:
    """Data class for match results."""
    matched: bool
    confidence: float
    transaction: Optional[Dict]
    match_type: str
    details: str

class TxIDMatcher:
    """Advanced TxID matcher for payment verification."""
    
    def __init__(self):
        self.confidence_thresholds = {
            'exact': 1.0,
            'high': 0.9,
            'medium': 0.7,
            'low': 0.5,
            'no_match': 0.0
        }
        
        # Time window for matching (in minutes)
        self.matching_time_window = 60  # 1 hour
    
    def normalize_txid(self, txid: str) -> str:
        """Normalize transaction ID for better matching."""
        if not txid:
            return ""
        
        # Remove common prefixes/suffixes and clean
        normalized = re.sub(r'^(txid:?|id:?)', '', str(txid).lower().strip())
        normalized = re.sub(r'[^0-9a-z]', '', normalized)
        return normalized
    
    def extract_all_possible_txids(self, transaction: Dict) -> List[str]:
        """Extract all possible transaction IDs from a transaction record."""
        txids = []
        
        # Primary TxID
        if transaction.get('tx_id'):
            txids.append(self.normalize_txid(transaction['tx_id']))
        
        # External transaction ID
        if transaction.get('external_tx_id'):
            txids.append(self.normalize_txid(transaction['external_tx_id']))
        
        # Extract from raw message using various patterns
        raw_message = transaction.get('raw_message', '')
        if raw_message:
            patterns = [
                r'TxId:\s*(\d+)',
                r'Transaction Id:\s*(\d+)',
                r'Financial Transaction Id:\s*(\d+)',
                r'\*162\*TxId:(\d+)',
                r'External Transaction Id:\s*([^\s]+)',
                r'Id:\s*(\d+)'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, raw_message, re.IGNORECASE)
                for match in matches:
                    normalized = self.normalize_txid(match)
                    if normalized and normalized not in txids:
                        txids.append(normalized)
        
        return list(set(txids))  # Remove duplicates
    
    def calculate_string_similarity(self, str1: str, str2: str) -> float:
        """Calculate similarity between two strings."""
        if not str1 or not str2:
            return 0.0
        
        return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()
    
    def find_exact_match(self, target_txid: str, transactions: List[Dict]) -> Optional[MatchResult]:
        """Find exact TxID match."""
        normalized_target = self.normalize_txid(target_txid)
        if not normalized_target:
            return None
        
        for transaction in transactions:
            txids = self.extract_all_possible_txids(transaction)
            
            for txid in txids:
                if normalized_target == txid:
                    return MatchResult(
                        matched=True,
                        confidence=1.0,
                        transaction=transaction,
                        match_type='exact',
                        details=f'Exact match found for TxID: {target_txid}'
                    )
        
        return None
    
    def find_fuzzy_match(self, target_txid: str, transactions: List[Dict], 
                        min_confidence: float = 0.8) -> Optional[MatchResult]:
        """Find fuzzy TxID match using string similarity."""
        normalized_target = self.normalize_txid(target_txid)
        if not normalized_target:
            return None
        
        best_match = None
        best_confidence = 0.0
        
        for transaction in transactions:
            txids = self.extract_all_possible_txids(transaction)
            
            for txid in txids:
                similarity = self.calculate_string_similarity(normalized_target, txid)
                
                if similarity > best_confidence and similarity >= min_confidence:
                    best_confidence = similarity
                    best_match = transaction
        
        if best_match and best_confidence >= min_confidence:
            match_type = 'high' if best_confidence >= 0.9 else 'medium'
            return MatchResult(
                matched=True,
                confidence=best_confidence,
                transaction=best_match,
                match_type=match_type,
                details=f'Fuzzy match found with {best_confidence:.2%} confidence'
            )
        
        return None
    
    def find_time_based_match(self, target_txid: str, verification_time: datetime, 
                            transactions: List[Dict]) -> Optional[MatchResult]:
        """Find match based on time proximity when TxID match is not exact."""
        # Look for transactions around the verification time
        time_window_start = verification_time - timedelta(minutes=self.matching_time_window)
        time_window_end = verification_time + timedelta(minutes=self.matching_time_window)
        
        candidates = []
        
        for transaction in transactions:
            tx_time = transaction.get('timestamp')
            if isinstance(tx_time, str):
                try:
                    tx_time = datetime.fromisoformat(tx_time.replace('Z', '+00:00'))
                except:
                    continue
            
            if tx_time and time_window_start <= tx_time <= time_window_end:
                # Calculate time-based confidence
                time_diff = abs((tx_time - verification_time).total_seconds()) / 60  # minutes
                time_confidence = max(0.0, 1.0 - (time_diff / self.matching_time_window))
                
                # Also consider partial TxID similarity
                txids = self.extract_all_possible_txids(transaction)
                max_txid_similarity = 0.0
                
                normalized_target = self.normalize_txid(target_txid)
                for txid in txids:
                    similarity = self.calculate_string_similarity(normalized_target, txid)
                    max_txid_similarity = max(max_txid_similarity, similarity)
                
                # Combined confidence (time + partial TxID match)
                combined_confidence = (time_confidence * 0.6) + (max_txid_similarity * 0.4)
                
                candidates.append((transaction, combined_confidence, time_diff))
        
        if candidates:
            # Sort by confidence, then by time proximity
            candidates.sort(key=lambda x: (x[1], -x[2]), reverse=True)
            best_transaction, confidence, time_diff = candidates[0]
            
            if confidence >= 0.6:  # Minimum threshold for time-based matching
                return MatchResult(
                    matched=True,
                    confidence=confidence,
                    transaction=best_transaction,
                    match_type='time_based',
                    details=f'Time-based match found {time_diff:.1f} minutes away with {confidence:.2%} confidence'
                )
        
        return None
    
    def find_match(self, target_txid: str, transactions: List[Dict], 
                   verification_time: datetime = None) -> MatchResult:
        """Main matching function that tries multiple strategies."""
        if not target_txid or not transactions:
            return MatchResult(
                matched=False,
                confidence=0.0,
                transaction=None,
                match_type='no_input',
                details='No TxID provided or no transactions to search'
            )
        
        if verification_time is None:
            verification_time = datetime.now()
        
        # Strategy 1: Exact match
        exact_match = self.find_exact_match(target_txid, transactions)
        if exact_match:
            logger.info(f"Exact match found for TxID: {target_txid}")
            return exact_match
        
        # Strategy 2: Fuzzy match
        fuzzy_match = self.find_fuzzy_match(target_txid, transactions)
        if fuzzy_match:
            logger.info(f"Fuzzy match found for TxID: {target_txid}")
            return fuzzy_match
        
        # Strategy 3: Time-based match (last resort)
        time_match = self.find_time_based_match(target_txid, verification_time, transactions)
        if time_match:
            logger.info(f"Time-based match found for TxID: {target_txid}")
            return time_match
        
        # No match found
        return MatchResult(
            matched=False,
            confidence=0.0,
            transaction=None,
            match_type='no_match',
            details=f'No suitable match found for TxID: {target_txid}'
        )
    
    def verify_transaction_details(self, match_result: MatchResult, 
                                 expected_amount: Optional[float] = None) -> Dict:
        """Verify additional transaction details beyond TxID matching."""
        if not match_result.matched or not match_result.transaction:
            return {
                'verified': False,
                'reason': 'No transaction match found',
                'confidence': 0.0
            }
        
        transaction = match_result.transaction
        verification_score = match_result.confidence
        issues = []
        
        # Check amount if provided
        if expected_amount is not None:
            tx_amount = transaction.get('amount', 0)
            if abs(tx_amount - expected_amount) > 0.01:  # Allow small floating point differences
                issues.append(f"Amount mismatch: expected {expected_amount}, found {tx_amount}")
                verification_score *= 0.5  # Reduce confidence significantly
        
        # Check if transaction is recent (within reasonable time)
        tx_time = transaction.get('timestamp')
        if tx_time:
            if isinstance(tx_time, str):
                try:
                    tx_time = datetime.fromisoformat(tx_time.replace('Z', '+00:00'))
                except:
                    tx_time = None
            
            if tx_time:
                time_diff = (datetime.now() - tx_time).total_seconds() / 3600  # hours
                if time_diff > 24:  # More than 24 hours old
                    issues.append(f"Transaction is {time_diff:.1f} hours old")
                    verification_score *= 0.8
        
        # Check transaction type (should be payment_out or similar)
        tx_type = transaction.get('message_type')
        if tx_type in ['payment_in', 'transfer_in']:  # These are incoming, might be less relevant for payment verification
            issues.append(f"Transaction type '{tx_type}' might not be a customer payment")
            verification_score *= 0.9
        
        return {
            'verified': verification_score >= 0.7 and len(issues) == 0,
            'confidence': verification_score,
            'issues': issues,
            'transaction_details': {
                'tx_id': transaction.get('tx_id'),
                'amount': transaction.get('amount'),
                'timestamp': transaction.get('timestamp'),
                'type': transaction.get('message_type'),
                'sender': transaction.get('sender_name'),
                'receiver': transaction.get('receiver_name')
            }
        }
    
    def generate_verification_report(self, target_txid: str, match_result: MatchResult, 
                                   verification_result: Dict) -> Dict:
        """Generate comprehensive verification report."""
        return {
            'target_txid': target_txid,
            'match_found': match_result.matched,
            'match_confidence': match_result.confidence,
            'match_type': match_result.match_type,
            'match_details': match_result.details,
            'verification_passed': verification_result.get('verified', False),
            'verification_confidence': verification_result.get('confidence', 0.0),
            'issues': verification_result.get('issues', []),
            'transaction': verification_result.get('transaction_details'),
            'timestamp': datetime.now().isoformat(),
            'recommendation': self._get_verification_recommendation(match_result, verification_result)
        }
    
    def _get_verification_recommendation(self, match_result: MatchResult, 
                                       verification_result: Dict) -> str:
        """Get recommendation based on matching and verification results."""
        if not match_result.matched:
            return "Transaction not found - request customer to check TxID or try again later"
        
        if verification_result.get('verified', False):
            if match_result.confidence >= 0.95:
                return "Payment verified successfully - proceed with order"
            else:
                return "Payment likely verified - proceed with caution"
        else:
            issues = verification_result.get('issues', [])
            if issues:
                return f"Verification failed: {'; '.join(issues[:2])}"
            else:
                return "Verification failed - manual review recommended"

# Test function
def test_matcher():
    """Test the TxID matcher."""
    matcher = TxIDMatcher()
    
    # Mock transactions database
    transactions = [
        {
            'tx_id': '22004556853',
            'amount': 1100.0,
            'timestamp': datetime.now() - timedelta(minutes=30),
            'message_type': 'payment_out',
            'sender_name': 'John Doe',
            'receiver_name': 'Assia Itangishaka',
            'raw_message': 'TxId: 22004556853. Your payment of 1,100 RWF to Assia Itangishaka...'
        },
        {
            'tx_id': '22021392902',
            'amount': 600.0,
            'timestamp': datetime.now() - timedelta(hours=2),
            'message_type': 'payment_out',
            'sender_name': 'John Doe',
            'receiver_name': 'Elyse',
            'raw_message': 'TxId: 22021392902. Your payment of 600 RWF to Elys e...'
        }
    ]
    
    # Test cases
    test_cases = [
        {'txid': '22004556853', 'expected_amount': 1100.0},
        {'txid': '22004556854', 'expected_amount': 1100.0},  # Similar but wrong
        {'txid': '22021392902', 'expected_amount': 500.0},   # Wrong amount
        {'txid': '99999999999', 'expected_amount': 1000.0}   # Not found
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n=== Test Case {i} ===")
        match_result = matcher.find_match(test_case['txid'], transactions)
        verification_result = matcher.verify_transaction_details(match_result, test_case['expected_amount'])
        report = matcher.generate_verification_report(test_case['txid'], match_result, verification_result)
        
        print(json.dumps(report, indent=2, default=str))

if __name__ == "__main__":
    test_matcher()
