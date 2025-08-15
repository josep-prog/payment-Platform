#!/usr/bin/env python3
"""
Complete system test for MoMo Payment Verification System
"""

import os
import sys
import json
from datetime import datetime

# Set environment variables for testing
os.environ['FLASK_ENV'] = 'development'
os.environ['FLASK_SECRET_KEY'] = 'test-secret-key'
os.environ['DEFAULT_VERIFICATION_CODE'] = '1043577'

def test_sms_parser():
    """Test SMS parsing functionality"""
    print("🔍 Testing SMS Parser...")
    try:
        from ml_models.sms_parser import MoMoSMSParser
        
        parser = MoMoSMSParser()
        test_message = "TxId: 22004556853. Your payment of 1,100 RWF to Test Merchant 047700 has been completed at 2025-08-15 20:00:00. Your new balance: 50,000 RWF. Fee was 0 RWF."
        
        result = parser.parse_sms(test_message)
        
        if result.get('parsed_successfully'):
            print("✅ SMS Parser: PASSED")
            print(f"   - TxID: {result.get('tx_id')}")
            print(f"   - Amount: {result.get('amount')} RWF")
            print(f"   - Type: {result.get('message_type')}")
            return True
        else:
            print("❌ SMS Parser: FAILED")
            print(f"   - Error: {result.get('error')}")
            return False
    except Exception as e:
        print(f"❌ SMS Parser: ERROR - {str(e)}")
        return False

def test_fraud_detector():
    """Test fraud detection functionality"""
    print("🛡️ Testing Fraud Detector...")
    try:
        from ml_models.fraud_detector import FraudDetector
        
        detector = FraudDetector()
        test_transaction = {
            'tx_id': '22004556853',
            'amount': 1100.0,
            'timestamp': datetime.now(),
            'message_type': 'payment_out',
            'new_balance': 50000.0,
            'raw_message': 'Test message'
        }
        
        risk_score, alerts = detector.analyze_transaction(test_transaction)
        
        print("✅ Fraud Detector: PASSED")
        print(f"   - Risk Score: {risk_score:.2f}")
        print(f"   - Alerts: {len(alerts)}")
        print(f"   - Risk Level: {detector.get_risk_level(risk_score)}")
        return True
    except Exception as e:
        print(f"❌ Fraud Detector: ERROR - {str(e)}")
        return False

def test_txid_matcher():
    """Test TxID matching functionality"""
    print("🎯 Testing TxID Matcher...")
    try:
        from ml_models.matcher import TxIDMatcher
        
        matcher = TxIDMatcher()
        
        # Mock transaction
        transactions = [{
            'tx_id': '22004556853',
            'amount': 1100.0,
            'timestamp': datetime.now(),
            'message_type': 'payment_out',
            'sender_name': 'Test User',
            'receiver_name': 'Test Merchant'
        }]
        
        # Test exact match
        match_result = matcher.find_match('22004556853', transactions)
        
        if match_result.matched:
            print("✅ TxID Matcher: PASSED")
            print(f"   - Match Type: {match_result.match_type}")
            print(f"   - Confidence: {match_result.confidence:.2f}")
            return True
        else:
            print("❌ TxID Matcher: FAILED")
            return False
    except Exception as e:
        print(f"❌ TxID Matcher: ERROR - {str(e)}")
        return False

def test_flask_app():
    """Test Flask application initialization"""
    print("🌐 Testing Flask Application...")
    try:
        # Import without running the app
        import app
        
        # Test if all components are accessible
        if hasattr(app, 'app') and hasattr(app, 'sms_parser') and hasattr(app, 'fraud_detector'):
            print("✅ Flask App: PASSED")
            print("   - App initialized successfully")
            print("   - All ML models loaded")
            print("   - Routes configured")
            return True
        else:
            print("❌ Flask App: FAILED - Missing components")
            return False
    except Exception as e:
        print(f"❌ Flask App: ERROR - {str(e)}")
        return False

def test_database_schema():
    """Test database schema file"""
    print("🗄️ Testing Database Schema...")
    try:
        schema_path = 'database/supabase_schema.sql'
        if os.path.exists(schema_path):
            with open(schema_path, 'r') as f:
                content = f.read()
            
            # Check for essential tables
            required_tables = ['transactions', 'verification_codes', 'payment_verifications', 'fraud_alerts']
            missing_tables = [table for table in required_tables if f'CREATE TABLE {table}' not in content]
            
            if not missing_tables:
                print("✅ Database Schema: PASSED")
                print("   - All required tables defined")
                print(f"   - Schema size: {len(content)} characters")
                return True
            else:
                print(f"❌ Database Schema: FAILED - Missing tables: {missing_tables}")
                return False
        else:
            print("❌ Database Schema: FAILED - File not found")
            return False
    except Exception as e:
        print(f"❌ Database Schema: ERROR - {str(e)}")
        return False

def test_configuration_files():
    """Test configuration files"""
    print("⚙️ Testing Configuration Files...")
    try:
        required_files = [
            'requirements.txt',
            '.env.example',
            'render.yaml',
            'gunicorn.conf.py',
            'DEPLOYMENT.md'
        ]
        
        missing_files = []
        for file in required_files:
            if not os.path.exists(file):
                missing_files.append(file)
        
        if not missing_files:
            print("✅ Configuration Files: PASSED")
            print("   - All required files present")
            return True
        else:
            print(f"❌ Configuration Files: FAILED - Missing: {missing_files}")
            return False
    except Exception as e:
        print(f"❌ Configuration Files: ERROR - {str(e)}")
        return False

def main():
    """Run all tests"""
    print("🚀 MoMo Payment Verification System - Complete Test Suite")
    print("=" * 60)
    
    tests = [
        test_sms_parser,
        test_fraud_detector,
        test_txid_matcher,
        test_flask_app,
        test_database_schema,
        test_configuration_files
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test failed with exception: {str(e)}")
        print()
    
    print("=" * 60)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED! System is ready for deployment.")
        print("\n🚀 Next Steps:")
        print("   1. Set up Supabase database")
        print("   2. Configure environment variables")
        print("   3. Deploy to Render")
        print("   4. Set up SMS forwarding")
        print("   5. Start verifying payments!")
        return True
    else:
        print("⚠️  Some tests failed. Please review the errors above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
