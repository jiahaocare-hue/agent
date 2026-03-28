---
skill_name: google_mail
dependencies:
  - email_config
---

# Google邮箱发送能力

## 能力描述

通过 Google 邮箱发送邮件。

## 脚本

- 脚本路径: scripts/send_google_mail.py

## 参数

- to: 收件人邮箱
- subject: 邮件主题
- content: 邮件内容
- sender: 发送人信息（从 email_config 获取）

## 使用方式

调用脚本时需要提供收件人邮箱、邮件主题和邮件内容。发送人信息会从 email_config 自动获取。
