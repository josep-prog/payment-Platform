-- Supabase Database Schema for MoMo Payment Verification System
-- This schema handles transactions, verification codes, and fraud detection

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create enum types for transaction categories
CREATE TYPE transaction_type AS ENUM (
    'payment_out',      -- User paying to someone/service
    'payment_in',       -- User receiving payment
    'transfer_out',     -- User transferring to someone
    'transfer_in',      -- User receiving transfer
    'withdrawal',       -- Cash withdrawal via agent
    'airtime',          -- Airtime/bundle purchase
    'electricity'       -- Utility payment
);

CREATE TYPE transaction_status AS ENUM (
    'pending',
    'verified',
    'failed',
    'suspicious'
);

-- Main transactions table
CREATE TABLE transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tx_id VARCHAR(50) UNIQUE NOT NULL,
    message_type transaction_type NOT NULL,
    amount DECIMAL(12,2) NOT NULL,
    fee DECIMAL(12,2) DEFAULT 0,
    sender_name VARCHAR(255),
    sender_phone VARCHAR(20),
    receiver_name VARCHAR(255),
    receiver_phone VARCHAR(20),
    receiver_code VARCHAR(50),
    new_balance DECIMAL(12,2),
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    raw_message TEXT NOT NULL,
    external_tx_id VARCHAR(255),
    token VARCHAR(255),
    message_from_sender TEXT,
    agent_name VARCHAR(255),
    agent_phone VARCHAR(20),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Verification codes table (for business payment verification)
CREATE TABLE verification_codes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code VARCHAR(20) UNIQUE NOT NULL,
    business_name VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Payment verifications table (links verification codes with transactions)
CREATE TABLE payment_verifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    verification_code_id UUID REFERENCES verification_codes(id),
    transaction_id UUID REFERENCES transactions(id),
    tx_id VARCHAR(50) NOT NULL,
    status transaction_status DEFAULT 'pending',
    verified_at TIMESTAMP WITH TIME ZONE,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Fraud detection table
CREATE TABLE fraud_alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    transaction_id UUID REFERENCES transactions(id),
    alert_type VARCHAR(100) NOT NULL,
    risk_score DECIMAL(5,3) NOT NULL,
    description TEXT,
    is_resolved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- SMS processing logs
CREATE TABLE sms_processing_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    raw_message TEXT NOT NULL,
    parsed_successfully BOOLEAN NOT NULL,
    error_message TEXT,
    transaction_id UUID REFERENCES transactions(id),
    processing_time_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for better performance
CREATE INDEX idx_transactions_tx_id ON transactions(tx_id);
CREATE INDEX idx_transactions_timestamp ON transactions(timestamp);
CREATE INDEX idx_transactions_sender_phone ON transactions(sender_phone);
CREATE INDEX idx_transactions_receiver_phone ON transactions(receiver_phone);
CREATE INDEX idx_payment_verifications_tx_id ON payment_verifications(tx_id);
CREATE INDEX idx_payment_verifications_status ON payment_verifications(status);
CREATE INDEX idx_verification_codes_code ON verification_codes(code);

-- Insert the default verification code for the business
INSERT INTO verification_codes (code, business_name) VALUES ('1043577', 'Default Business Payment Portal');

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Add triggers for updated_at columns
CREATE TRIGGER update_transactions_updated_at BEFORE UPDATE ON transactions 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_verification_codes_updated_at BEFORE UPDATE ON verification_codes 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- RLS (Row Level Security) policies for multi-tenancy if needed
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE verification_codes ENABLE ROW LEVEL SECURITY;
ALTER TABLE payment_verifications ENABLE ROW LEVEL SECURITY;

-- Create policies (adjust based on your authentication needs)
CREATE POLICY "Allow all operations for authenticated users" ON transactions
    FOR ALL USING (auth.role() = 'authenticated');

CREATE POLICY "Allow all operations for authenticated users" ON verification_codes
    FOR ALL USING (auth.role() = 'authenticated');

CREATE POLICY "Allow all operations for authenticated users" ON payment_verifications
    FOR ALL USING (auth.role() = 'authenticated');
