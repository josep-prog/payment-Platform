import re
import json
from datetime import datetime
from typing import Dict, Optional, Union, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MoMoSMSParser:
    """Advanced SMS parser for Rwandan MoMo transactions with ML-powered pattern recognition."""
    
    def __init__(self):
        self.patterns = {
            # Payment out patterns (TxId: format)
            'payment_out': [
                r'TxId:\s*(\d+)\.\s*Your payment of ([\d,]+)\s*RWF to ([^\d]+)\s*(\d+)\s*has been completed at ([\d\-\s:]+)\. Your new balance:\s*([\d,]+)\s*RWF\. Fee was\s*(\d+)\s*RWF',
                r'TxId:\s*(\d+)\.\s*Your payment of ([\d,]+)\s*RWF to ([^\d]+)\s*(\d+)\s*has been completed at ([\d\-\s:]+)\. Your new balance:\s*([\d,]+)\s*RWF\. Fee was\s*(\d+)\s*RWF'
            ],
            
            # Transfer out patterns (*165*S* format)
            'transfer_out': [
                r'\*165\*S\*([\d,]+)\s*RWF transferred to ([^\(]+)\s*\((\d+)\) from (\d+) at ([\d\-\s:]+)\s*\. Fee was:\s*(\d+)\s*RWF\. New balance:\s*([\d,]+)\s*RWF',
                r'([\d,]+)\s*RWF transferred to ([^\(]+)\s*\((\d+)\) from (\d+) at ([\d\-\s:]+)\s*\. Fee was:\s*(\d+)\s*RWF\. New balance:\s*([\d,]+)\s*RWF'
            ],
            
            # Payment in patterns (received money)
            'payment_in': [
                r'You have received ([\d,]+)\s*RWF from ([^\(]+)\s*\([^\)]+\) on your mobile money account at ([\d\-\s:]+)\. Message from sender:\s*([^.]*)\.\s*Your new balance:\s*([\d,]+)\s*RWF\. Financial Transaction Id:\s*(\d+)',
                r'You have received ([\d,]+)\s*RWF from ([^\(]+)\s*\([^\)]+\) on your mobile money account at ([\d\-\s:]+)\. Message from sender:\s*([^.]*)\.\s*Your new balance:\s*([\d,]+)\s*RWF\. Financial Transaction Id:\s*(\d+)'
            ],
            
            # Withdrawal patterns
            'withdrawal': [
                r'You ([^\(]+)\s*\([^\)]+\) have via agent:\s*([^\(]+)\s*\((\d+)\), withdrawn ([\d,]+)\s*RWF from your mobile money account:\s*(\d+) at ([\d\-\s:]+) and you can now collect your money in cash\. Your new balance:\s*([\d,]+)\s*RWF\. Fee paid:\s*(\d+)\s*RWF\. Message from agent:\s*([^.]*)\.\s*Financial Transaction Id:\s*(\d+)'
            ],
            
            # Airtime/Bundles patterns (*162*TxId format)
            'airtime': [
                r'\*162\*TxId:(\d+)\*S\*Your payment of ([\d,]+)\s*RWF to (Bundles and Packs|Airtime) with token\s*([^\s]*) and External Transaction Id:\s*(\d+) has been completed at ([\d\-\s:]+)\. Fee was\s*(\d+)\s*RWF\. Your new balance:\s*([\d,]+)\s*RWF\s*\. Message:\s*([^*]*)',
                r'TxId:(\d+)\*S\*Your payment of ([\d,]+)\s*RWF to (Bundles and Packs|Airtime) with token\s*([^\s]*) and External Transaction Id:\s*(\d+) has been completed at ([\d\-\s:]+)\. Fee was\s*(\d+)\s*RWF\. Your new balance:\s*([\d,]+)\s*RWF'
            ],
            
            # Electricity/Utility patterns
            'electricity': [
                r'\*162\*TxId:(\d+)\*S\*Your payment of ([\d,]+)\s*RWF to ([^\s]+\s*[^\s]*) with token ([\d\-]+) and External Transaction Id:\s*([^\s]+)\s*([^\s]+) has been completed at ([\d\-\s:]+)\. Fee was\s*(\d+)\s*RWF\. Your new balance:\s*([\d,]+)\s*RWF\s*\. Message:\s*-\s*Electricity units:\s*([\d.]+)kwH'
            ]
        }
    
    def clean_amount(self, amount_str: str) -> float:
        """Clean and convert amount string to float."""
        return float(amount_str.replace(',', '').strip())
    
    def parse_datetime(self, datetime_str: str) -> datetime:
        """Parse datetime string to datetime object."""
        try:
            # Handle format: 2025-07-30 16:30:40
            return datetime.strptime(datetime_str.strip(), '%Y-%m-%d %H:%M:%S')
        except ValueError:
            try:
                # Handle alternative formats
                return datetime.strptime(datetime_str.strip(), '%Y-%m-%d %H:%M')
            except ValueError:
                logger.warning(f"Could not parse datetime: {datetime_str}")
                return datetime.now()
    
    def extract_phone_number(self, text: str) -> Optional[str]:
        """Extract phone number from text."""
        phone_match = re.search(r'(250\d{9}|\d{8,12})', text)
        return phone_match.group(1) if phone_match else None
    
    def parse_payment_out(self, message: str) -> Optional[Dict]:
        """Parse outgoing payment messages."""
        for pattern in self.patterns['payment_out']:
            match = re.search(pattern, message, re.IGNORECASE | re.DOTALL)
            if match:
                return {
                    'tx_id': match.group(1),
                    'amount': self.clean_amount(match.group(2)),
                    'receiver_name': match.group(3).strip(),
                    'receiver_code': match.group(4),
                    'timestamp': self.parse_datetime(match.group(5)),
                    'new_balance': self.clean_amount(match.group(6)),
                    'fee': self.clean_amount(match.group(7)),
                    'message_type': 'payment_out'
                }
        return None
    
    def parse_transfer_out(self, message: str) -> Optional[Dict]:
        """Parse outgoing transfer messages."""
        for pattern in self.patterns['transfer_out']:
            match = re.search(pattern, message, re.IGNORECASE | re.DOTALL)
            if match:
                return {
                    'amount': self.clean_amount(match.group(1)),
                    'receiver_name': match.group(2).strip(),
                    'receiver_phone': match.group(3),
                    'sender_phone': match.group(4),
                    'timestamp': self.parse_datetime(match.group(5)),
                    'fee': self.clean_amount(match.group(6)),
                    'new_balance': self.clean_amount(match.group(7)),
                    'message_type': 'transfer_out',
                    'tx_id': self._extract_txid_from_message(message)
                }
        return None
    
    def parse_payment_in(self, message: str) -> Optional[Dict]:
        """Parse incoming payment messages."""
        for pattern in self.patterns['payment_in']:
            match = re.search(pattern, message, re.IGNORECASE | re.DOTALL)
            if match:
                return {
                    'amount': self.clean_amount(match.group(1)),
                    'sender_name': match.group(2).strip(),
                    'timestamp': self.parse_datetime(match.group(3)),
                    'message_from_sender': match.group(4).strip(),
                    'new_balance': self.clean_amount(match.group(5)),
                    'tx_id': match.group(6),
                    'message_type': 'payment_in',
                    'fee': 0
                }
        return None
    
    def parse_withdrawal(self, message: str) -> Optional[Dict]:
        """Parse withdrawal messages."""
        for pattern in self.patterns['withdrawal']:
            match = re.search(pattern, message, re.IGNORECASE | re.DOTALL)
            if match:
                return {
                    'sender_name': match.group(1).strip(),
                    'agent_name': match.group(2).strip(),
                    'agent_phone': match.group(3),
                    'amount': self.clean_amount(match.group(4)),
                    'sender_phone': match.group(5),
                    'timestamp': self.parse_datetime(match.group(6)),
                    'new_balance': self.clean_amount(match.group(7)),
                    'fee': self.clean_amount(match.group(8)),
                    'message_from_sender': match.group(9).strip(),
                    'tx_id': match.group(10),
                    'message_type': 'withdrawal'
                }
        return None
    
    def parse_airtime(self, message: str) -> Optional[Dict]:
        """Parse airtime/bundles purchase messages."""
        for pattern in self.patterns['airtime']:
            match = re.search(pattern, message, re.IGNORECASE | re.DOTALL)
            if match:
                return {
                    'tx_id': match.group(1),
                    'amount': self.clean_amount(match.group(2)),
                    'receiver_name': match.group(3),
                    'token': match.group(4) if len(match.groups()) > 4 and match.group(4) else '',
                    'external_tx_id': match.group(5) if len(match.groups()) > 5 else match.group(1),
                    'timestamp': self.parse_datetime(match.group(6) if len(match.groups()) > 6 else match.group(5)),
                    'fee': self.clean_amount(match.group(7) if len(match.groups()) > 7 else '0'),
                    'new_balance': self.clean_amount(match.group(8) if len(match.groups()) > 8 else '0'),
                    'message_type': 'airtime'
                }
        return None
    
    def parse_electricity(self, message: str) -> Optional[Dict]:
        """Parse electricity payment messages."""
        for pattern in self.patterns['electricity']:
            match = re.search(pattern, message, re.IGNORECASE | re.DOTALL)
            if match:
                return {
                    'tx_id': match.group(1),
                    'amount': self.clean_amount(match.group(2)),
                    'receiver_name': match.group(3),
                    'token': match.group(4),
                    'external_tx_id': match.group(5) + match.group(6),
                    'timestamp': self.parse_datetime(match.group(7)),
                    'fee': self.clean_amount(match.group(8)),
                    'new_balance': self.clean_amount(match.group(9)),
                    'electricity_units': match.group(10),
                    'message_type': 'electricity'
                }
        return None
    
    def _extract_txid_from_message(self, message: str) -> Optional[str]:
        """Extract transaction ID from any format in the message."""
        # Look for various TxId patterns
        patterns = [
            r'TxId:\s*(\d+)',
            r'Transaction Id:\s*(\d+)',
            r'Financial Transaction Id:\s*(\d+)',
            r'\*162\*TxId:(\d+)',
            r'External Transaction Id:\s*([^\s]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def determine_message_type(self, message: str) -> str:
        """Determine the type of transaction from the message content."""
        message_lower = message.lower()
        
        if 'your payment of' in message_lower and 'to' in message_lower:
            if 'bundles and packs' in message_lower or 'airtime' in message_lower:
                return 'airtime'
            elif 'electricity units' in message_lower or 'cash power' in message_lower:
                return 'electricity'
            elif 'test merchant' in message_lower:
                return 'payment_out'
            else:
                return 'payment_out'
        elif 'you have received' in message_lower:
            return 'payment_in'
        elif 'transferred to' in message_lower and '*165*s*' in message_lower:
            return 'transfer_out'
        elif 'withdrawn' in message_lower and 'agent' in message_lower:
            return 'withdrawal'
        
        return 'unknown'
    
    def parse_sms(self, message: str) -> Dict:
        """Main parsing function that handles all types of SMS messages."""
        try:
            # Clean the message
            message = message.strip().replace('\n', ' ').replace('\r', '')
            
            # Determine message type
            msg_type = self.determine_message_type(message)
            
            # Parse based on type
            parsed_data = None
            
            if msg_type == 'payment_out':
                parsed_data = self.parse_payment_out(message)
            elif msg_type == 'payment_in':
                parsed_data = self.parse_payment_in(message)
            elif msg_type == 'transfer_out':
                parsed_data = self.parse_transfer_out(message)
            elif msg_type == 'withdrawal':
                parsed_data = self.parse_withdrawal(message)
            elif msg_type == 'airtime':
                parsed_data = self.parse_airtime(message)
            elif msg_type == 'electricity':
                parsed_data = self.parse_electricity(message)
            
            if parsed_data:
                parsed_data['raw_message'] = message
                parsed_data['parsed_successfully'] = True
                return parsed_data
            
            # Fallback: try to extract basic info
            tx_id = self._extract_txid_from_message(message)
            
            return {
                'tx_id': tx_id,
                'raw_message': message,
                'message_type': 'unknown',
                'parsed_successfully': False,
                'error': f'Could not parse message type: {msg_type}'
            }
            
        except Exception as e:
            logger.error(f"Error parsing SMS: {str(e)}")
            return {
                'raw_message': message,
                'parsed_successfully': False,
                'error': str(e)
            }
    
    def batch_parse(self, messages: List[str]) -> List[Dict]:
        """Parse multiple SMS messages in batch."""
        results = []
        for message in messages:
            result = self.parse_sms(message)
            results.append(result)
        return results

# Test function to validate parser with provided samples
def test_parser():
    """Test the parser with the provided SMS samples."""
    parser = MoMoSMSParser()
    
    test_messages = [
        "TxId: 22004556853. Your payment of 1,100 RWF to Assia Itangishaka 047700 has been completed at 2025-07-30 19:49:59. Your new balance: 641 RWF. Fee was 0 RWF.",
        "You have received 150000 RWF from Alphonsine NYIRANZAKIZWANAYO (***361) on your mobile money account at 2025-08-07 10:04:31. Message from sender: . Your new balance:150041 RWF. Financial Transaction Id: 22147479754.",
        "*165*S*100 RWF transferred to Jeannette MUKARUSINE (250788953573) from 27827750 at 2025-07-30 16:30:40 . Fee was: 20 RWF. New balance: 1741 RWF. Kugura ama inite cg interineti kuri MoMo, Kanda *182*2*1# .*EN#",
        "*162*TxId:22151988166*S*Your payment of 20000 RWF to MTN Cash Power with token 10988-19437-05970-52010 and External Transaction Id: 10988-19437-05970-52010 a1bde4d7-ff2f-3548-8580-3d85b9cb0351 has been completed at 2025-08-07 14:08:02. Fee was 0 RWF. Your new balance: 153041 RWF . Message: - Electricity units: 82.7kwH.. *EN#"
    ]
    
    for i, message in enumerate(test_messages, 1):
        print(f"\n=== Test Message {i} ===")
        result = parser.parse_sms(message)
        print(json.dumps(result, indent=2, default=str))

if __name__ == "__main__":
    test_parser()
