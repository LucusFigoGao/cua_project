"""
入口脚本：连接固定沙箱实例，部署 Hub、跑一条真实 task 的完整闭环、验证模型调用。
"""
import os

from gym.utils import create_llm_caller, SandboxEnv

SANDBOX_ID = "edvcir3u2sbf3bigeg52ibdvkwkkx7htijlfbshy"
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "./configs/sandbox_config.json")


def main():
    env = SandboxEnv.connect(SANDBOX_ID, hub_base_url="http://localhost:5173")
    env.save_config(CONFIG_PATH)
    print("已连接实例:", env.sbx.sandbox_id)

    env.deploy_hub_app("notion_mock", port=5173)
    print("notion_mock 已就绪")

    task = env.find_task(app_type="notion_mock")
    print("task:", task)

    task_dir = env.download_task(
        task_id=task["task_id"],
        url_placeholder="__CUA_GYM_NOTION_URL__",
        url_value="http://localhost:5173",
    )

    sid = env.run_initial_setup(task_dir)
    print("sid:", sid)
    env.save_config(CONFIG_PATH)

    screenshot = env.screenshot(sid, local_out="task_initial.png")
    print("截图已保存到本地 task_initial.png，字节数:", len(screenshot))

    reward = env.run_reward(task_dir)
    print("REWARD:", reward)

    llm = create_llm_caller(
        model="gpt-5",
        api_key=os.environ["ICHAT_API_KEY"],
        # base_url="http://ichat.woa.com/api/external",
        base_url=os.environ["ICHAT_BASE_URL"],
    )
    reply = llm.call_llm(prompt="Hello!", system_content="You are a helpful assistant.")
    print("模型回复:", reply)


if __name__ == "__main__":
    main()