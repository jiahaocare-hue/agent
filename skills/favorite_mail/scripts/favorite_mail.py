"""
收藏邮件脚本
"""
import argparse
import json

def main():
    parser = argparse.ArgumentParser(description='收藏邮件')
    parser.add_argument('--mail_id', required=True, help='邮件ID')
    
    args = parser.parse_args()
    
    result = {
        "status": "success",
        "mail_id": args.mail_id,
        "message": f"邮件 {args.mail_id} 已添加到收藏夹"
    }
    
    print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    main()
