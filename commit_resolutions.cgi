#!/usr/bin/env python3
"""
Academic Senate Resolutions SQLite CGI Endpoint
File: cgi-bin/commit_resolutions.cgi
Permissions: chmod +x cgi-bin/commit_resolutions.cgi
"""

import sys
import os
import json
import sqlite3

# ----------------------------------------------------------------------
# Enforce UTF-8 Encoding on CGI Environment & Standard I/O Streams
# ----------------------------------------------------------------------
os.environ['PYTHONIOENCODING'] = 'utf-8'

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stdin, 'reconfigure'):
    sys.stdin.reconfigure(encoding='utf-8', errors='replace')

# Define SQLite database location
DB_PATH = os.path.join(os.path.dirname(__file__), "resolutions.db")


def send_response(data, status=200):
    """Sends JSON responses with proper CGI headers and UTF-8 encoding."""
    sys.stdout.write(f"Status: {status}\n")
    sys.stdout.write("Content-Type: application/json; charset=utf-8\n")
    sys.stdout.write("Access-Control-Allow-Origin: *\n")
    sys.stdout.write("Access-Control-Allow-Headers: Content-Type\n")
    sys.stdout.write("Access-Control-Allow-Methods: POST, GET, OPTIONS\n\n")

    try:
        sys.stdout.write(json.dumps(data, ensure_ascii=False))
    except UnicodeEncodeError:
        # Safe fallback if system output strictly enforces ASCII characters
        sys.stdout.write(json.dumps(data, ensure_ascii=True))

    sys.stdout.flush()
    sys.exit(0)


# Handle CORS preflight requests immediately
if os.environ.get('REQUEST_METHOD') == 'OPTIONS':
    send_response({"status": "ok"})


def init_db():
    """Initializes SQLite database and creates the resolutions table."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS resolutions (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            text TEXT,
            status TEXT CHECK(status IN ('Passed', 'Failed', 'No Action Taken')) NOT NULL,
            category TEXT,
            sponsor TEXT,
            meeting_date TEXT,
            source_doc TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    return conn


def sanitize_text(text):
    """Encodes and decodes string to replace invalid unicode surrogates or bad encodings."""
    if not isinstance(text, str):
        return text
    return text.encode('utf-8', errors='surrogateescape').decode('utf-8', errors='ignore')


def main():
    try:
        method = os.environ.get('REQUEST_METHOD', 'GET')

        if method == 'GET':
            conn = init_db()
            cursor = conn.cursor()
            cursor.execute('SELECT id, title, text, status, category, sponsor, meeting_date, source_doc FROM resolutions ORDER BY id DESC')
            rows = cursor.fetchall()
            conn.close()

            resolutions = []
            for r in rows:
                resolutions.append({
                    "id": r[0],
                    "title": r[1],
                    "text": r[2],
                    "status": r[3],
                    "category": r[4],
                    "sponsor": r[5],
                    "meeting_date": r[6],
                    "source_doc": r[7]
                })
            send_response({"resolutions": resolutions})

        elif method == 'POST':
            length = int(os.environ.get('CONTENT_LENGTH', 0))
            if length > 0:
                raw_bytes = sys.stdin.buffer.read(length)
                body = raw_bytes.decode('utf-8', errors='replace')
            else:
                body = "{}"

            payload = json.loads(body)
            items = payload.get("resolutions", [])

            if not items:
                send_response({"error": "No resolutions provided"}, status=400)

            conn = init_db()
            cursor = conn.cursor()
            inserted = 0

            for res in items:
                clean_id = sanitize_text(res.get('id'))
                clean_title = sanitize_text(res.get('title', 'Untitled Resolution'))
                clean_text = sanitize_text(res.get('text', ''))
                clean_status = sanitize_text(res.get('status', 'No Action Taken'))
                clean_category = sanitize_text(res.get('category', 'Governance'))
                clean_sponsor = sanitize_text(res.get('sponsor', 'Academic Senate Executive Council'))
                clean_date = sanitize_text(res.get('meeting_date', ''))
                clean_doc = sanitize_text(res.get('source_doc', 'PDF Upload'))

                # INSERT OR REPLACE handles universal SQLite updates across all versions
                cursor.execute('''
                    INSERT OR REPLACE INTO resolutions 
                    (id, title, text, status, category, sponsor, meeting_date, source_doc)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    clean_id,
                    clean_title,
                    clean_text,
                    clean_status,
                    clean_category,
                    clean_sponsor,
                    clean_date,
                    clean_doc
                ))
                inserted += 1

            conn.commit()
            conn.close()
            send_response({"message": "Successfully committed to SQLite", "count": inserted})

    except Exception as e:
        # Intercept runtime errors and send structured JSON output
        send_response({"error": f"Server CGI Error: {str(e)}"}, status=500)


if __name__ == '__main__':
    main()
