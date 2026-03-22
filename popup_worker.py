import sys
import json
import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Dict


def show_workflow_popup(task_id: int, workflow_description: str, workflow_json_str: str):
    result = {"action": "cancelled", "modification": None}

    def on_approve():
        result["action"] = "approved"
        root.destroy()

    def on_cancel():
        result["action"] = "cancelled"
        root.destroy()

    def on_modify():
        modification = modification_text.get("1.0", tk.END).strip()
        if modification:
            result["action"] = "modify"
            result["modification"] = modification
            root.destroy()
        else:
            messagebox.showwarning("提示", "请输入修改意见")

    root = tk.Tk()
    root.title(f"任务 {task_id} - 工作流确认")
    root.geometry("500x400")
    root.attributes("-topmost", True)

    ttk.Label(root, text="即将执行以下操作：", font=("Arial", 12, "bold")).pack(pady=10)

    desc_frame = ttk.Frame(root)
    desc_frame.pack(fill=tk.BOTH, expand=True, padx=20)

    desc_text = tk.Text(
        desc_frame,
        height=8,
        width=50,
        wrap=tk.WORD,
        font=("Arial", 10),
        state=tk.NORMAL
    )
    desc_text.pack(fill=tk.BOTH, expand=True)
    desc_text.insert(tk.END, workflow_description or "无描述")
    desc_text.config(state=tk.DISABLED)

    ttk.Label(root, text="修改意见（可选）：").pack(pady=(10, 0))
    modification_text = tk.Text(root, height=3, width=50, wrap=tk.WORD)
    modification_text.pack(pady=5)

    button_frame = ttk.Frame(root)
    button_frame.pack(pady=10)

    ttk.Button(button_frame, text="确认执行", command=on_approve).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="取消", command=on_cancel).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="提交修改", command=on_modify).pack(side=tk.LEFT, padx=5)

    def on_close():
        result["action"] = "cancelled"
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()

    print(json.dumps(result, ensure_ascii=False))


def show_missing_params_popup(missing_params: List[str], reply_message: str):
    result = {"action": "cancelled", "params": {}}

    def on_confirm():
        params = {}
        for param, entry in entries.items():
            value = entry.get().strip()
            if not value:
                messagebox.showwarning("提示", f"请输入 {param}")
                return
            params[param] = value
        result["action"] = "confirmed"
        result["params"] = params
        root.destroy()

    def on_cancel():
        result["action"] = "cancelled"
        result["params"] = {}
        root.destroy()

    root = tk.Tk()
    root.title("请补充信息")
    root.geometry("400x300")
    root.attributes("-topmost", True)

    ttk.Label(root, text=reply_message or "请补充以下信息：", wraplength=350).pack(pady=10)

    entries = {}
    for param in missing_params:
        frame = ttk.Frame(root)
        frame.pack(fill=tk.X, padx=20, pady=5)
        ttk.Label(frame, text=f"{param}:").pack(side=tk.LEFT)
        entry = ttk.Entry(frame, width=30)
        entry.pack(side=tk.RIGHT)
        entries[param] = entry

    button_frame = ttk.Frame(root)
    button_frame.pack(pady=10)

    ttk.Button(button_frame, text="确认", command=on_confirm).pack(side=tk.LEFT, padx=50)
    ttk.Button(button_frame, text="取消", command=on_cancel).pack(side=tk.RIGHT, padx=50)

    def on_close():
        result["action"] = "cancelled"
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    try:
        input_data = sys.stdin.read()
        payload = json.loads(input_data)

        popup_type = payload.get("type", "workflow")

        if popup_type == "missing_params":
            missing_params = payload.get("missing_params", [])
            reply_message = payload.get("reply_message", "请补充以下信息：")
            show_missing_params_popup(missing_params, reply_message)
        else:
            task_id = int(payload.get("task_id", 0))
            workflow_description = payload.get("description", "")
            workflow_json_str = payload.get("workflow_json", "{}")
            show_workflow_popup(task_id, workflow_description, workflow_json_str)

    except Exception as e:
        print(f"弹窗进程解析数据失败: {e}", file=sys.stderr)
        print(json.dumps({"action": "cancelled", "modification": None}))
        sys.exit(1)
