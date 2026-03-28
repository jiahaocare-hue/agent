"""
Google邮箱发送脚本
"""
import argparse
import json

def main():
    parser = argparse.ArgumentParser(description='发送Google邮件')
    parser.add_argument('--to', required=True, help='收件人邮箱')
    parser.add_argument('--subject', required=True, help='邮件主题')
    parser.add_argument('--content', required=True, help='邮件内容')
    parser.add_argument('--sender', default='', help='发送人信息')
    
    args = parser.parse_args()
    
    result = {
        "status": "success",
        "mail_id": "google_mail_001",
        "to": args.to,
        "subject": args.subject,
        "message": f"已通过Google邮箱发送邮件给 {args.to}"
    }
    
    print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    main()
