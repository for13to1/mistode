# 贡献指南

感谢您对 Mistode 项目的关注！我们欢迎各种形式的贡献。

## 开发环境设置

1. 克隆项目：

   ```shell
   git clone https://github.com/for13to1/mistode.git
   cd mistode
   ```

2. 安装开发依赖：

   ```shell
   pip install -e ".[dev]"
   ```

3. 运行测试：

   ```shell
   pytest tests/ -v
   ```

## 代码规范

- 使用 Black 格式化代码：`black src/ tests/`
- 使用 isort 排序导入：`isort src/ tests/`
- 使用 flake8 检查代码质量：`flake8 src/ tests/`

## 提交代码

1. 创建功能分支：`git checkout -b feature/your-feature-name`
2. 提交更改：`git commit -m "描述你的更改"`
3. 推送到远程：`git push origin feature/your-feature-name`
4. 创建 Pull Request

## 报告问题

请在 GitHub Issues 中报告 bug 或提出功能建议，包括：

- 问题描述
- 复现步骤
- 期望行为
- 实际行为
- 环境信息

## 开发流程

1. 确保所有测试通过
2. 添加新功能的测试用例
3. 更新文档
4. 遵循现有的代码风格
