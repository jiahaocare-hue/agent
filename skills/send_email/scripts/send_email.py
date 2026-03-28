#!/usr/bin/env python3
"""发送邮件（模拟）"""
import sys
import json

def send_email(to: str, subject: str, body: str) -> dict:
    """发送邮件（模拟）"""
    return {
        "status": "sent",
        "to": to,
        "subject": subject,
        "body": body,
        "message_id": f"msg_{hash(to + subject) % 10000}"
    }

def main():
    if len(sys.argv) < 4:
        print(json.dumps({"error": "用法: send_email.py <to> <subject> <body>"}))
        return
    
    to, subject, body = sys.argv[1], sys.argv[2], sys.argv[3]
    result = send_email(to, subject, body)
    print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    main()
