---
skill_name: favorite_mail
---

# 收藏邮件能力

## 能力描述

将邮件添加到收藏夹。

## 脚本

- 脚本路径: scripts/favorite_mail.py

## 参数

- mail_id: 邮件ID

## 使用方式

调用脚本时需要提供邮件ID。可以引用前序节点的输出，如 `${{ state.node_outputs.step_1_send.mail_id }}`。
