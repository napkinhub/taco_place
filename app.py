import os
import json
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from flask import Flask, jsonify, request, send_from_directory

DATABASE_URL = os.environ.get("DATABASE_URL")

app = Flask(__name__, static_folder=".", static_url_path="")


@contextmanager
def get_conn():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS checks (
                id SERIAL PRIMARY KEY,
                platform TEXT,
                item_type TEXT,
                sale_price NUMERIC,
                market_price NUMERIC,
                payment_method TEXT,
                deal_type TEXT,
                chat_text TEXT,
                score INTEGER,
                verdict TEXT,
                scam_types JSONB,
                reasons JSONB,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        conn.commit()


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/api/checks", methods=["POST"])
def create_check():
    body = request.get_json(silent=True) or {}

    required_types = {
        "score": int,
        "verdict": str,
    }
    for field, expected_type in required_types.items():
        if field not in body:
            return jsonify({"error": f"missing field: {field}"}), 400

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO checks
                (platform, item_type, sale_price, market_price, payment_method,
                 deal_type, chat_text, score, verdict, scam_types, reasons)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, created_at
            """,
            (
                body.get("platform"),
                body.get("itemType"),
                body.get("salePrice"),
                body.get("marketPrice"),
                body.get("paymentMethod"),
                body.get("dealType"),
                body.get("chatText"),
                body.get("score"),
                body.get("verdict"),
                json.dumps(body.get("scamTypes", [])),
                json.dumps(body.get("reasons", [])),
            ),
        )
        row = cur.fetchone()
        conn.commit()

    return jsonify({"id": row[0], "created_at": row[1].isoformat()}), 201


@app.route("/api/checks", methods=["GET"])
def list_checks():
    limit = min(int(request.args.get("limit", 20)), 100)

    with get_conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id, platform, item_type, sale_price, market_price, payment_method,
                   deal_type, score, verdict, scam_types, reasons, created_at
            FROM checks
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall()

    for row in rows:
        row["created_at"] = row["created_at"].isoformat()

    return jsonify(rows)


@app.route("/api/checks/<int:check_id>", methods=["GET"])
def get_check(check_id):
    with get_conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM checks WHERE id = %s", (check_id,))
        row = cur.fetchone()

    if row is None:
        return jsonify({"error": "not found"}), 404

    row["created_at"] = row["created_at"].isoformat()
    return jsonify(row)


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
