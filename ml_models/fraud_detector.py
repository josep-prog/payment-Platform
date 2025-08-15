import re
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class FraudAlert:
    """Data class for fraud alerts."""
    alert_type: str
    risk_score: float
    description: str
    severity: str  # 'low', 'medium', 'high', 'critical'

class FraudDetector:
    """Advanced fraud detection system for MoMo transactions."""
    
    def __init__(self):
        self.risk_thresholds = {
            'low': 0.3,
            'medium': 0.6,
            'high': 0.8,
            'critical': 0.95
        }
        
        # Fraud patterns and rules
        self.fraud_rules = {
            'duplicate_txid': {'weight': 0.9, 'description': 'Duplicate transaction ID detected'},
            'unusual_amount': {'weight': 0.7, 'description': 'Amount significantly higher than usual pattern'},
            'rapid_transactions': {'weight': 0.8, 'description': 'Multiple transactions in short time period'},
            'suspicious_timing': {'weight': 0.6, 'description': 'Transaction at unusual time'},
            'amount_pattern': {'weight': 0.7, 'description': 'Suspicious amount pattern detected'},
            'phone_mismatch': {'weight': 0.8, 'description': 'Phone number inconsistency detected'},
            'balance_inconsistency': {'weight': 0.9, 'description': 'Balance calculation doesn\'t match'},
            'message_tampering': {'weight': 0.95, 'description': 'Potential message tampering detected'}
        }
    
    def check_duplicate_txid(self, tx_id: str, existing_transactions: List[Dict]) -> Optional[FraudAlert]:
        """Check for duplicate transaction IDs."""
        if not tx_id:
            return None
            
        duplicates = [t for t in existing_transactions if t.get('tx_id') == tx_id]
        if len(duplicates) > 1:
            return FraudAlert(
                alert_type='duplicate_txid',
                risk_score=self.fraud_rules['duplicate_txid']['weight'],
                description=f"Transaction ID {tx_id} appears {len(duplicates)} times",
                severity='critical'
            )
        return None
    
    def check_unusual_amount(self, amount: float, user_history: List[Dict]) -> Optional[FraudAlert]:
        """Check for unusually high amounts compared to user's history."""
        if not user_history or amount <= 0:
            return None
        
        amounts = [t.get('amount', 0) for t in user_history if t.get('amount', 0) > 0]
        if not amounts:
            return None
        
        avg_amount = sum(amounts) / len(amounts)
        max_amount = max(amounts)
        
        # Check if current amount is significantly higher than average
        if amount > avg_amount * 10 or amount > max_amount * 2:
            risk_score = min(0.9, (amount / avg_amount) / 15)  # Cap at 0.9
            return FraudAlert(
                alert_type='unusual_amount',
                risk_score=risk_score,
                description=f"Amount {amount} RWF is {amount/avg_amount:.1f}x higher than average ({avg_amount:.0f} RWF)",
                severity='high' if risk_score > 0.8 else 'medium'
            )
        return None
    
    def check_rapid_transactions(self, timestamp: datetime, recent_transactions: List[Dict]) -> Optional[FraudAlert]:
        """Check for rapid succession of transactions."""
        if not recent_transactions:
            return None
        
        # Look for transactions in the last 5 minutes
        five_minutes_ago = timestamp - timedelta(minutes=5)
        recent = [t for t in recent_transactions 
                 if t.get('timestamp') and t.get('timestamp') > five_minutes_ago]
        
        if len(recent) >= 5:  # More than 5 transactions in 5 minutes
            return FraudAlert(
                alert_type='rapid_transactions',
                risk_score=min(0.9, len(recent) * 0.15),
                description=f"{len(recent)} transactions in the last 5 minutes",
                severity='high'
            )
        return None
    
    def check_suspicious_timing(self, timestamp: datetime) -> Optional[FraudAlert]:
        """Check for transactions at suspicious times (e.g., late night)."""
        hour = timestamp.hour
        
        # Consider transactions between 2 AM and 5 AM as suspicious
        if 2 <= hour <= 5:
            return FraudAlert(
                alert_type='suspicious_timing',
                risk_score=0.6,
                description=f"Transaction at {hour}:00 (late night)",
                severity='medium'
            )
        return None
    
    def check_amount_patterns(self, amount: float) -> Optional[FraudAlert]:
        """Check for suspicious amount patterns."""
        # Round numbers might be suspicious for certain amounts
        if amount >= 10000 and amount % 1000 == 0 and amount >= 50000:
            return FraudAlert(
                alert_type='amount_pattern',
                risk_score=0.7,
                description=f"Large round number amount: {amount} RWF",
                severity='medium'
            )
        
        # Very specific amounts might be test transactions
        if amount in [1.0, 10.0, 100.0, 1000.0]:
            return FraudAlert(
                alert_type='amount_pattern',
                risk_score=0.4,
                description=f"Potentially test amount: {amount} RWF",
                severity='low'
            )
        
        return None
    
    def check_balance_consistency(self, transaction: Dict) -> Optional[FraudAlert]:
        """Check if balance calculations are consistent."""
        amount = transaction.get('amount', 0)
        fee = transaction.get('fee', 0)
        new_balance = transaction.get('new_balance')
        message_type = transaction.get('message_type')
        
        if not new_balance or not amount:
            return None
        
        # For complex balance checking, we'd need previous balance
        # This is a basic check for obvious inconsistencies
        if message_type in ['payment_out', 'transfer_out'] and new_balance < 0:
            return FraudAlert(
                alert_type='balance_inconsistency',
                risk_score=0.9,
                description=f"Negative balance after {message_type}: {new_balance} RWF",
                severity='critical'
            )
        
        return None
    
    def check_message_tampering(self, transaction: Dict) -> Optional[FraudAlert]:
        """Check for potential message tampering indicators."""
        raw_message = transaction.get('raw_message', '')
        
        # Look for unusual characters or formatting
        suspicious_patterns = [
            r'[^\w\s\-\.\*:#(),]+',  # Unusual characters
            r'\d+\.\d{3,}',  # Too many decimal places
            r'(RWF.*RWF)',  # Multiple RWF mentions in unusual way
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, raw_message):
                return FraudAlert(
                    alert_type='message_tampering',
                    risk_score=0.8,
                    description=f"Suspicious pattern in message: {pattern}",
                    severity='high'
                )
        
        return None
    
    def analyze_transaction(self, transaction: Dict, user_history: List[Dict] = None, 
                          existing_transactions: List[Dict] = None) -> Tuple[float, List[FraudAlert]]:
        """Comprehensive fraud analysis of a transaction."""
        alerts = []
        
        # Get transaction details
        tx_id = transaction.get('tx_id')
        amount = transaction.get('amount', 0)
        timestamp = transaction.get('timestamp')
        
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except:
                timestamp = datetime.now()
        
        # Run all fraud checks
        checks = [
            self.check_duplicate_txid(tx_id, existing_transactions or []),
            self.check_unusual_amount(amount, user_history or []),
            self.check_rapid_transactions(timestamp, user_history or []),
            self.check_suspicious_timing(timestamp),
            self.check_amount_patterns(amount),
            self.check_balance_consistency(transaction),
            self.check_message_tampering(transaction)
        ]
        
        # Filter out None results
        alerts = [alert for alert in checks if alert is not None]
        
        # Calculate overall risk score
        if not alerts:
            overall_risk = 0.0
        else:
            risk_scores = [alert.risk_score for alert in alerts]
            # Use weighted average with emphasis on highest risks
            overall_risk = sum(risk_scores) / len(risk_scores)
            # Boost if multiple alerts
            if len(alerts) > 1:
                overall_risk = min(1.0, overall_risk * 1.2)
        
        return overall_risk, alerts
    
    def get_risk_level(self, risk_score: float) -> str:
        """Convert risk score to risk level."""
        if risk_score >= self.risk_thresholds['critical']:
            return 'critical'
        elif risk_score >= self.risk_thresholds['high']:
            return 'high'
        elif risk_score >= self.risk_thresholds['medium']:
            return 'medium'
        elif risk_score >= self.risk_thresholds['low']:
            return 'low'
        else:
            return 'safe'
    
    def should_block_transaction(self, risk_score: float) -> bool:
        """Determine if transaction should be blocked based on risk score."""
        return risk_score >= self.risk_thresholds['critical']
    
    def generate_fraud_report(self, transaction: Dict, risk_score: float, 
                            alerts: List[FraudAlert]) -> Dict:
        """Generate a comprehensive fraud analysis report."""
        risk_level = self.get_risk_level(risk_score)
        should_block = self.should_block_transaction(risk_score)
        
        return {
            'transaction_id': transaction.get('tx_id'),
            'risk_score': risk_score,
            'risk_level': risk_level,
            'should_block': should_block,
            'alerts_count': len(alerts),
            'alerts': [
                {
                    'type': alert.alert_type,
                    'score': alert.risk_score,
                    'description': alert.description,
                    'severity': alert.severity
                } for alert in alerts
            ],
            'timestamp': datetime.now().isoformat(),
            'recommendation': self._get_recommendation(risk_level, should_block)
        }
    
    def _get_recommendation(self, risk_level: str, should_block: bool) -> str:
        """Get recommendation based on risk assessment."""
        if should_block:
            return "Block transaction and require manual review"
        elif risk_level == 'high':
            return "Flag for manual review before processing"
        elif risk_level == 'medium':
            return "Monitor transaction and log for analysis"
        elif risk_level == 'low':
            return "Proceed with caution and log"
        else:
            return "Proceed normally"

# Test function
def test_fraud_detector():
    """Test the fraud detection system."""
    detector = FraudDetector()
    
    # Test transaction
    test_transaction = {
        'tx_id': '22004556853',
        'amount': 150000.0,  # Large amount
        'timestamp': datetime(2025, 8, 15, 2, 30, 0),  # Late night
        'message_type': 'payment_out',
        'new_balance': 50000.0,
        'raw_message': 'TxId: 22004556853. Your payment of 150,000 RWF...'
    }
    
    # Mock user history with smaller amounts
    user_history = [
        {'amount': 1000, 'timestamp': datetime.now() - timedelta(days=1)},
        {'amount': 2000, 'timestamp': datetime.now() - timedelta(days=2)},
        {'amount': 1500, 'timestamp': datetime.now() - timedelta(days=3)}
    ]
    
    risk_score, alerts = detector.analyze_transaction(test_transaction, user_history)
    report = detector.generate_fraud_report(test_transaction, risk_score, alerts)
    
    print("Fraud Detection Test Results:")
    print(json.dumps(report, indent=2, default=str))

if __name__ == "__main__":
    test_fraud_detector()
