# 一、Ubuntu git

1. 首次使用，配置身份

```bash
# 设置提交代码时的全局用户名
git config --global user.name "你的GitHub用户名"

# 设置提交代码时的全局邮箱
git config --global user.email "你的GitHub注册邮箱"
```

2. 生成与配置SSH密钥

```
# 生成 SSH 密钥（⚠️ 重要：提示输入保存路径时，直接按回车！不要自己打字命名！）
ssh-keygen -t ed25519 -C "你的GitHub注册邮箱"

# 启动 SSH 代理
eval "$(ssh-agent -s)"

# 将私钥添加到代理中
ssh-add ~/.ssh/id_ed25519

# 打印并复制公钥（将输出的整段 ssh-ed25519 开头的内容复制，去 GitHub 网页 Settings -> SSH keys 中添加）
cat ~/.ssh/id_ed25519.pub
```

3. 连接测试与仓库关联

```
# 测试 SSH 连接（输入 yes 回车，⚠️ 必须看到 "Hi 你的用户名!"，如果名字不对说明 GitHub 绑错账号了）
ssh -T git@github.com

# 查看当前仓库的远程地址
git remote -v

# ⚠️ 如果显示的是 https:// 开头，需修改为 SSH 格式（把用户名和仓库名换成你自己的）
git remote set-url origin git@github.com:你的GitHub用户名/你的仓库名.git
```

4. 日常开发提交流程

```
git add .
git commit -m ""
git push origin main
```

