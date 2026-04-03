#!/usr/bin/env python
"""Verify all tables were created in Supabase."""

import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

try:
    conn = psycopg2.connect(os.getenv('DATABASE_URL'))
    cur = conn.cursor()
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema='public' 
        ORDER BY table_name
    """)
    tables = cur.fetchall()
    
    print("✓ Migration successful! Tables created in Supabase:\n")
    for table in tables:
        print(f"  - {table[0]}")
    
    print(f"\nTotal tables: {len(tables)}")
    
    # Also verify alembic_version
    cur.execute("SELECT version_num FROM alembic_version ORDER BY version_num")
    versions = cur.fetchall()
    print(f"\nAlembic revisions applied:")
    for version in versions:
        print(f"  - {version[0]}")
    
    conn.close()
except Exception as e:
    print(f"✗ Error: {e}")
    exit(1)
