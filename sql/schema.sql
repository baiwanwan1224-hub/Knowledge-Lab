-- Knowledge Lab · PostgreSQL Schema
-- Run: psql -h localhost -U n8n -d n8n_scraper -f schema.sql

CREATE TABLE IF NOT EXISTS quiz_sessions (
    id SERIAL PRIMARY KEY,
    session_uuid VARCHAR(32) UNIQUE NOT NULL,
    session_name VARCHAR(255),
    topics JSONB DEFAULT '[]',
    question_types JSONB DEFAULT '[]',
    question_count INTEGER DEFAULT 5,
    difficulty VARCHAR(20) DEFAULT 'medium',
    total_questions INTEGER DEFAULT 0,
    questions_correct INTEGER DEFAULT 0,
    questions_wrong INTEGER DEFAULT 0,
    score_percentage DECIMAL(5,1) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'ready',
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS questions (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES quiz_sessions(id),
    question_text TEXT,
    question_type VARCHAR(30),
    correct_answer TEXT,
    explanation TEXT,
    knowledge_point VARCHAR(255),
    source_note VARCHAR(255),
    difficulty VARCHAR(20) DEFAULT 'medium',
    quality_score DECIMAL(3,2) DEFAULT 0
);

CREATE TABLE IF NOT EXISTS answers (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES quiz_sessions(id),
    question_id INTEGER REFERENCES questions(id),
    user_answer TEXT,
    score DECIMAL(3,1) DEFAULT 0,
    max_score DECIMAL(3,1) DEFAULT 5,
    is_correct BOOLEAN DEFAULT false,
    grader_feedback TEXT,
    weakness_tags JSONB DEFAULT '[]',
    misunderstanding VARCHAR(500),
    answer_timestamp TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS wrong_answers (
    id SERIAL PRIMARY KEY,
    question_id INTEGER REFERENCES questions(id),
    question_text TEXT,
    user_answer TEXT,
    correct_answer TEXT,
    explanation TEXT,
    weakness_tags JSONB DEFAULT '[]',
    topics JSONB DEFAULT '[]',
    review_count INTEGER DEFAULT 0,
    next_review_at TIMESTAMP,
    review_status VARCHAR(20) DEFAULT 'active',
    ease_factor DECIMAL(3,2) DEFAULT 2.50,
    obsidian_note_path VARCHAR(500),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS topic_mastery (
    id SERIAL PRIMARY KEY,
    topic_name VARCHAR(100) UNIQUE NOT NULL,
    mastery_score DECIMAL(5,1) DEFAULT 50,
    recent_accuracy DECIMAL(5,1) DEFAULT 0,
    total_attempted INTEGER DEFAULT 0,
    total_correct INTEGER DEFAULT 0,
    review_urgency VARCHAR(20) DEFAULT 'normal',
    last_quiz_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Views
CREATE OR REPLACE VIEW v_quiz_summary AS
SELECT
    DATE(created_at) as quiz_date,
    COUNT(*) as quiz_count,
    ROUND(AVG(score_percentage), 1) as avg_score,
    SUM(total_questions) as total_q
FROM quiz_sessions WHERE status = 'completed'
GROUP BY DATE(created_at) ORDER BY quiz_date DESC;

CREATE OR REPLACE VIEW v_weakness_summary AS
SELECT
    weakness_tag,
    COUNT(*) as occurrence_count,
    ROUND(AVG(score), 1) as avg_score
FROM (
    SELECT jsonb_array_elements_text(weakness_tags) as weakness_tag, score
    FROM answers WHERE weakness_tags IS NOT NULL AND jsonb_array_length(weakness_tags) > 0
) sub
GROUP BY weakness_tag ORDER BY occurrence_count DESC;

CREATE OR REPLACE VIEW v_daily_review AS
SELECT
    id, question_text, weakness_tags, topics,
    review_count, next_review_at, ease_factor
FROM wrong_answers
WHERE review_status = 'active' AND next_review_at <= NOW()
ORDER BY next_review_at ASC;
