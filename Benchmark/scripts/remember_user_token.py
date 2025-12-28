import json
import os

AUTH_FILE = '.auth/gitlab_state.json'

def patch_auth_file():
    if not os.path.exists(AUTH_FILE):
        print("❌ 文件不存在")
        return

    with open(AUTH_FILE, 'r') as f:
        data = json.load(f)

    patched = False
    # 找到 remember_user_token 的过期时间作为参考
    long_expiry = next((c['expires'] for c in data['cookies'] if c['name'] == 'remember_user_token'), 1799392098)

    for cookie in data['cookies']:
        # 如果是 session cookie 且是临时效期 (-1)
        if cookie['name'] == '_gitlab_session' and cookie['expires'] == -1:
            print(f"🔧 正在修补 Cookie: {cookie['name']}")
            print(f"   原过期时间: {cookie['expires']}")
            cookie['expires'] = long_expiry # 赋予它长久的生命
            print(f"   新过期时间: {cookie['expires']}")
            patched = True
    
    if patched:
        with open(AUTH_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"✅ 成功！{AUTH_FILE} 已更新，Session Cookie 现已持久化。")
    else:
        print("👌 无需修补，未发现过期的 Session Cookie。")

if __name__ == "__main__":
    patch_auth_file()