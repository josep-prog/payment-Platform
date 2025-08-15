import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_cors import CORS
from supabase import create_client, Client
from dotenv import load_dotenv

# Import our ML models
from ml_models.sms_parser import MoMoSMSParser
from ml_models.fraud_detector import FraudDetector
from ml_models.matcher import TxIDMatcher

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
CORS(app)  # Enable CORS for all routes

# Initialize Supabase client
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_ANON_KEY')

if not supabase_url or not supabase_key:
    logger.error("Supabase credentials not found. Please check your .env file.")
    supabase = None
else:
    supabase: Client = create_client(supabase_url, supabase_key)
    logger.info("Supabase client initialized successfully")

# Initialize ML models
sms_parser = MoMoSMSParser()
fraud_detector = FraudDetector()
txid_matcher = TxIDMatcher()

# Default verification code
DEFAULT_VERIFICATION_CODE = '1043577'

class DatabaseManager:
    """Handles database operations with Supabase."""
    
    @staticmethod
    def store_transaction(transaction_data: Dict) -> Optional[str]:
        """Store parsed transaction in database."""
        if not supabase:
            logger.error("Supabase client not available")
            return None
        
        try:
            # Insert transaction
            response = supabase.table('transactions').insert(transaction_data).execute()
            
            if response.data:
                transaction_id = response.data[0]['id']
                logger.info(f"Transaction stored successfully: {transaction_id}")
                return transaction_id
            else:
                logger.error(f"Failed to store transaction: {response}")
                return None
                
        except Exception as e:
            logger.error(f"Error storing transaction: {str(e)}")
            return None
    
    @staticmethod
    def get_transactions_by_txid(tx_id: str) -> List[Dict]:
        """Get transactions by TxID."""
        if not supabase:
            return []
        
        try:
            response = supabase.table('transactions').select('*').eq('tx_id', tx_id).execute()
            return response.data if response.data else []
        except Exception as e:
            logger.error(f"Error fetching transactions by TxID: {str(e)}")
            return []
    
    @staticmethod
    def get_recent_transactions(hours: int = 24) -> List[Dict]:
        """Get recent transactions."""
        if not supabase:
            return []
        
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            response = (supabase.table('transactions')
                       .select('*')
                       .gte('timestamp', cutoff_time.isoformat())
                       .order('timestamp', desc=True)
                       .execute())
            return response.data if response.data else []
        except Exception as e:
            logger.error(f"Error fetching recent transactions: {str(e)}")
            return []
    
    @staticmethod
    def store_verification_attempt(verification_data: Dict) -> Optional[str]:
        """Store payment verification attempt."""
        if not supabase:
            return None
        
        try:
            response = supabase.table('payment_verifications').insert(verification_data).execute()
            
            if response.data:
                verification_id = response.data[0]['id']
                logger.info(f"Verification attempt stored: {verification_id}")
                return verification_id
            else:
                logger.error(f"Failed to store verification attempt: {response}")
                return None
                
        except Exception as e:
            logger.error(f"Error storing verification attempt: {str(e)}")
            return None
    
    @staticmethod
    def store_fraud_alert(alert_data: Dict) -> Optional[str]:
        """Store fraud alert."""
        if not supabase:
            return None
        
        try:
            response = supabase.table('fraud_alerts').insert(alert_data).execute()
            
            if response.data:
                alert_id = response.data[0]['id']
                logger.info(f"Fraud alert stored: {alert_id}")
                return alert_id
            else:
                logger.error(f"Failed to store fraud alert: {response}")
                return None
                
        except Exception as e:
            logger.error(f"Error storing fraud alert: {str(e)}")
            return None
    
    @staticmethod
    def log_sms_processing(log_data: Dict) -> None:
        """Log SMS processing attempt."""
        if not supabase:
            return
        
        try:
            supabase.table('sms_processing_logs').insert(log_data).execute()
        except Exception as e:
            logger.error(f"Error logging SMS processing: {str(e)}")

db = DatabaseManager()

# API Routes

@app.route('/')
def index():
    """Main payment verification page."""
    return render_template('index.html', verification_code=DEFAULT_VERIFICATION_CODE)

@app.route('/api/health')
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'services': {
            'supabase': supabase is not None,
            'sms_parser': True,
            'fraud_detector': True,
            'txid_matcher': True
        }
    })

@app.route('/api/sms/process', methods=['POST'])
def process_sms():
    """Process incoming SMS message from Android forwarder."""
    start_time = datetime.now()
    
    try:
        # Get SMS data from request
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({
                'success': False,
                'error': 'No message provided'
            }), 400
        
        raw_message = data['message']
        sender = data.get('sender', 'Unknown')
        received_at = data.get('timestamp')
        
        if received_at:
            try:
                received_at = datetime.fromisoformat(received_at.replace('Z', '+00:00'))
            except:
                received_at = datetime.now()
        else:
            received_at = datetime.now()
        
        logger.info(f"Processing SMS from {sender}: {raw_message[:100]}...")
        
        # Parse the SMS
        parsed_data = sms_parser.parse_sms(raw_message)
        
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        if parsed_data.get('parsed_successfully'):
            # Prepare transaction data for database
            transaction_data = {
                'tx_id': parsed_data.get('tx_id'),
                'message_type': parsed_data.get('message_type'),
                'amount': parsed_data.get('amount', 0),
                'fee': parsed_data.get('fee', 0),
                'sender_name': parsed_data.get('sender_name'),
                'sender_phone': parsed_data.get('sender_phone'),
                'receiver_name': parsed_data.get('receiver_name'),
                'receiver_phone': parsed_data.get('receiver_phone'),
                'receiver_code': parsed_data.get('receiver_code'),
                'new_balance': parsed_data.get('new_balance'),
                'timestamp': parsed_data.get('timestamp') or received_at,
                'raw_message': raw_message,
                'external_tx_id': parsed_data.get('external_tx_id'),
                'token': parsed_data.get('token'),
                'message_from_sender': parsed_data.get('message_from_sender'),
                'agent_name': parsed_data.get('agent_name'),
                'agent_phone': parsed_data.get('agent_phone')
            }
            
            # Store transaction
            transaction_id = db.store_transaction(transaction_data)
            
            # Run fraud detection
            recent_transactions = db.get_recent_transactions(24)
            risk_score, fraud_alerts = fraud_detector.analyze_transaction(
                parsed_data, recent_transactions, recent_transactions
            )
            
            # Store fraud alerts if any
            if fraud_alerts:
                for alert in fraud_alerts:
                    alert_data = {
                        'transaction_id': transaction_id,
                        'alert_type': alert.alert_type,
                        'risk_score': alert.risk_score,
                        'description': alert.description
                    }
                    db.store_fraud_alert(alert_data)
            
            # Log processing
            log_data = {
                'raw_message': raw_message,
                'parsed_successfully': True,
                'transaction_id': transaction_id,
                'processing_time_ms': int(processing_time)
            }
            db.log_sms_processing(log_data)
            
            return jsonify({
                'success': True,
                'transaction_id': transaction_id,
                'parsed_data': parsed_data,
                'fraud_analysis': {
                    'risk_score': risk_score,
                    'alerts_count': len(fraud_alerts),
                    'should_block': fraud_detector.should_block_transaction(risk_score)
                },
                'processing_time_ms': processing_time
            })
        
        else:
            # Log failed parsing
            log_data = {
                'raw_message': raw_message,
                'parsed_successfully': False,
                'error_message': parsed_data.get('error', 'Unknown parsing error'),
                'processing_time_ms': int(processing_time)
            }
            db.log_sms_processing(log_data)
            
            return jsonify({
                'success': False,
                'error': 'Failed to parse SMS',
                'details': parsed_data.get('error'),
                'processing_time_ms': processing_time
            })
    
    except Exception as e:
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        logger.error(f"Error processing SMS: {str(e)}")
        
        # Log error
        if 'raw_message' in locals():
            log_data = {
                'raw_message': raw_message,
                'parsed_successfully': False,
                'error_message': str(e),
                'processing_time_ms': int(processing_time)
            }
            db.log_sms_processing(log_data)
        
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'processing_time_ms': processing_time
        }), 500

@app.route('/api/verify', methods=['POST'])
def verify_payment():
    """Verify payment using TxID."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        tx_id = data.get('tx_id', '').strip()
        verification_code = data.get('verification_code', '').strip()
        expected_amount = data.get('expected_amount')
        
        if not tx_id:
            return jsonify({
                'success': False,
                'error': 'Transaction ID is required'
            }), 400
        
        if not verification_code or verification_code != DEFAULT_VERIFICATION_CODE:
            return jsonify({
                'success': False,
                'error': 'Invalid verification code'
            }), 400
        
        logger.info(f"Verifying payment with TxID: {tx_id}")
        
        # Get recent transactions from database
        recent_transactions = db.get_recent_transactions(48)  # 48 hours window
        
        if not recent_transactions:
            return jsonify({
                'success': False,
                'error': 'No recent transactions found. Please ensure SMS forwarding is working.',
                'recommendation': 'Check your SMS forwarder app or try again later'
            })
        
        # Find matching transaction
        match_result = txid_matcher.find_match(tx_id, recent_transactions)
        
        # Verify transaction details
        verification_result = txid_matcher.verify_transaction_details(
            match_result, expected_amount
        )
        
        # Generate comprehensive report
        report = txid_matcher.generate_verification_report(
            tx_id, match_result, verification_result
        )
        
        # Store verification attempt
        verification_data = {
            'verification_code_id': None,  # We'd need to look up the verification code ID
            'transaction_id': match_result.transaction.get('id') if match_result.transaction else None,
            'tx_id': tx_id,
            'status': 'verified' if verification_result.get('verified') else 'failed',
            'verified_at': datetime.now() if verification_result.get('verified') else None,
            'ip_address': request.environ.get('REMOTE_ADDR'),
            'user_agent': request.environ.get('HTTP_USER_AGENT')
        }
        
        verification_id = db.store_verification_attempt(verification_data)
        
        # Prepare response
        response_data = {
            'success': verification_result.get('verified', False),
            'verification_id': verification_id,
            'report': report,
            'timestamp': datetime.now().isoformat()
        }
        
        if not verification_result.get('verified'):
            response_data['error'] = report.get('recommendation', 'Verification failed')
        
        return jsonify(response_data)
    
    except Exception as e:
        logger.error(f"Error verifying payment: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error during verification'
        }), 500

@app.route('/api/transactions/recent', methods=['GET'])
def get_recent_transactions():
    """Get recent transactions (admin endpoint)."""
    try:
        hours = int(request.args.get('hours', 24))
        limit = int(request.args.get('limit', 50))
        
        transactions = db.get_recent_transactions(hours)
        
        # Limit results
        if limit:
            transactions = transactions[:limit]
        
        return jsonify({
            'success': True,
            'count': len(transactions),
            'transactions': transactions
        })
    
    except Exception as e:
        logger.error(f"Error fetching recent transactions: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch transactions'
        }), 500

@app.route('/api/transactions/search', methods=['GET'])
def search_transactions():
    """Search transactions by TxID."""
    try:
        tx_id = request.args.get('tx_id', '').strip()
        
        if not tx_id:
            return jsonify({
                'success': False,
                'error': 'Transaction ID is required'
            }), 400
        
        transactions = db.get_transactions_by_txid(tx_id)
        
        return jsonify({
            'success': True,
            'count': len(transactions),
            'transactions': transactions
        })
    
    except Exception as e:
        logger.error(f"Error searching transactions: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Search failed'
        }), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get system statistics."""
    try:
        if not supabase:
            return jsonify({
                'success': False,
                'error': 'Database not available'
            }), 503
        
        # Get transaction stats
        transactions_response = supabase.table('transactions').select('id', 'message_type', 'amount', 'timestamp').execute()
        transactions = transactions_response.data if transactions_response.data else []
        
        # Get verification stats
        verifications_response = supabase.table('payment_verifications').select('id', 'status', 'created_at').execute()
        verifications = verifications_response.data if verifications_response.data else []
        
        # Calculate stats
        total_transactions = len(transactions)
        total_verifications = len(verifications)
        successful_verifications = len([v for v in verifications if v.get('status') == 'verified'])
        
        # Transaction types breakdown
        type_breakdown = {}
        for tx in transactions:
            tx_type = tx.get('message_type', 'unknown')
            type_breakdown[tx_type] = type_breakdown.get(tx_type, 0) + 1
        
        # Recent activity (last 24 hours)
        cutoff_time = datetime.now() - timedelta(hours=24)
        recent_transactions = [tx for tx in transactions 
                             if tx.get('timestamp') and 
                             datetime.fromisoformat(tx['timestamp'].replace('Z', '+00:00')) > cutoff_time]
        
        return jsonify({
            'success': True,
            'stats': {
                'total_transactions': total_transactions,
                'total_verifications': total_verifications,
                'successful_verifications': successful_verifications,
                'verification_success_rate': (successful_verifications / max(total_verifications, 1)) * 100,
                'recent_transactions_24h': len(recent_transactions),
                'transaction_types': type_breakdown
            },
            'timestamp': datetime.now().isoformat()
        })
    
    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to get statistics'
        }), 500

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Endpoint not found'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': 'Internal server error'
    }), 500

# Development routes for testing
if os.getenv('FLASK_ENV') == 'development':
    
    @app.route('/api/test/parse', methods=['POST'])
    def test_parse():
        """Test SMS parsing (development only)."""
        data = request.get_json()
        message = data.get('message', '')
        
        if not message:
            return jsonify({'error': 'No message provided'}), 400
        
        result = sms_parser.parse_sms(message)
        return jsonify(result)
    
    @app.route('/api/test/fraud', methods=['POST'])
    def test_fraud():
        """Test fraud detection (development only)."""
        data = request.get_json()
        transaction = data.get('transaction', {})
        
        risk_score, alerts = fraud_detector.analyze_transaction(transaction)
        report = fraud_detector.generate_fraud_report(transaction, risk_score, alerts)
        
        return jsonify(report)

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV') == 'development'
    
    logger.info(f"Starting MoMo Payment Verification System on port {port}")
    logger.info(f"Debug mode: {debug}")
    logger.info(f"Verification code: {DEFAULT_VERIFICATION_CODE}")
    
    app.run(host='0.0.0.0', port=port, debug=debug)
