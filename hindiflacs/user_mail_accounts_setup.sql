-- Script to create user_mail_accounts
CREATE TABLE IF NOT EXISTS user_mail_accounts (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    default_account CHAR(1) DEFAULT 'N',
    sort_order INTEGER DEFAULT 0
);

-- Insert a default test account (update email as necessary)
INSERT INTO user_mail_accounts (email, default_account, sort_order)
VALUES ('govardhanarao.s@gmail.com', 'Y', 1)
ON CONFLICT (email) DO NOTHING;

-- Just in case hindiflacs_songs was created previously without blomp_user_id:
ALTER TABLE hindiflacs_songs ADD COLUMN IF NOT EXISTS blomp_user_id INTEGER REFERENCES user_mail_accounts(id) ON DELETE SET NULL;
