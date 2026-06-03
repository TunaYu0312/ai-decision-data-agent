# AI Decision Data Agent

本项目是直销业务 AI Decision Data Agent 的 File Upload Mode MVP。它基于用户上传的脱敏 Excel / CSV 数据，自动识别 Sheet、字段和业务专题，完成专题分析、决策输出和互动 HTML 报告导出。

## MVP Scope

- 支持 `.xlsx` 多 Sheet 和 `.csv`。
- 上传文件不要求固定 Sheet 名和固定字段名；系统会基于字段别名、Sheet 名称和业务 Schema 自动推断。
- 默认入口是 `Auto Agent`，上传后可一键完成识别、分析和 HTML 报告。
- 支持五个业务专题：经销商业绩波动、订阅业务、Prysm IO、社群运营、产品及活动评估。
- 使用本地规则引擎计算指标和生成决策建议。
- 可选 LLM 增强只用于表达润色，不替代指标计算。
- 不连接 MaxCompute，不做 Text-to-SQL，不连接生产数据库。

## Setup

```powershell
cd "D:\AI Data Agent\ai_data_analysis_agent"
python -m pip install -r requirements.txt
python data_samples\generate_samples.py
python -m streamlit run app.py
```

打开后优先使用左侧 `Auto Agent` 页面。`Sample Workbooks` 页面提供 5 个虚拟 Excel，可用于测试完整流程。

## Test

```powershell
python -m pytest tests -q
```

## Output

- Markdown: `outputs/markdown/`
- HTML reports: `outputs/html_reports/`
