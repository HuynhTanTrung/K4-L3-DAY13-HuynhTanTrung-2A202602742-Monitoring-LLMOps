# Báo cáo cá nhân — K4-L3A Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Huỳnh Tấn Trung
- **MSSV:** 2A202602742
- **Lớp:** K4-L3A
- **Repository URL:** https://github.com/HuynhTanTrung/K4-L3-DAY13-HuynhTanTrung-2A202602742-Monitoring-LLMOps
- **Commit SHA cuối:**
- **Challenge ID:** day13-k4-l3a-monitoring-llmops-v1
- **Tên project Langfuse cá nhân:** `day13-k4-l3a-2A202602742`

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence            | Đường dẫn                             |
| ------------------- | ------------------------------------- |
| Pytest cuối         | `evidence/01-pytest.png`              |
| Log validator       | `evidence/02-log-validator.png`       |
| Dashboard validator | `evidence/03-dashboard-validator.png` |
| Structured log      | `evidence/04-structured-log.png`      |
| PII redaction       | `evidence/05-pii-redaction.png`       |
| Trace list          | `evidence/06-trace-list.png`          |
| Trace waterfall     | `evidence/07-trace-waterfall.png`     |
| Trace metadata      | `evidence/08-trace-metadata.png`      |
| Prompt versions     | `evidence/09-prompt-versions.png`     |
| Prompt rollback     | `evidence/10-prompt-rollback.png`     |
| Dashboard runtime   | `evidence/11-dashboard-overview.png`  |
| Incident metric     | `evidence/12-incident-metric.png`     |
| Incident log        | `evidence/13-incident-log.png`        |
| Incident trace      | `evidence/14-incident-trace.png`      |

## 3. Kết quả kỹ thuật

| Nội dung                | Baseline            | Kết quả cuối | Nhận xét |
| ----------------------- | ------------------- | ------------ | -------- |
| `validate_logs.py`      |                     | 100/100      |          |
| `validate_dashboard.py` |                     | 6/6          |          |
| `pytest`                | 2 failed, 20 passed | 22 passed    |          |
| Số traces hợp lệ        |                     | 30           |          |
| Số PII leak             |                     | 0            |          |
| Latency P95 / TTFT P95  |                     | 3824         |          |
| Retrieval success rate  |                     | 100%         |          |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** CorrelationIdMiddleware clear contextvars mỗi request, đọc header x-request-id nếu có, nếu không thì sinh req-<8-hex> từ uuid4(). Bind qua bind_contextvars(correlation_id=...), trả lại trong response header x-request-id và x-response-time-ms
- **Các metadata được ghi vào structured log:** Trong /chat, bind_contextvars(user_id_hash, session_id, feature, model, env) ngay đầu handler. Kèm correlation_id từ middleware. Mọi log record sau đó tự động có 6 field này nhờ merge_contextvars
- **Cách bảo đảm PII được scrub trước khi ghi:** scrub*event là processor trong logging_config.py, đứng trước JsonlFileProcessor và JSONRenderer. Nó chạy scrub_text trên mọi string trong payload và event, dùng regex trong pii.py để thay email/phone VN/CCCD/credit card bằng [REDACTED*\*]. summarize_text cũng scrub trước khi cắt preview
- **Cách kiểm chứng kết quả:** validate_logs.py → PII leaks detected: 0, score 100/100. Evidence: evidence/02-log-validator.png, evidence/05-pii-redaction.png

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** Project Langfuse day13-k4-l3a-2A202602742. Mỗi trace có tag lab, monitoring, claude-sonnet-4-5. Evidence: evidence/06-trace-list.png
- **Cấu trúc root/retrieval/generation observations:** Root lab-agent-run → child retrieval + child llm-call. Dùng decorator @observe(as_type=...) vì SDK v4 không expose start_as_current_span ở module level
- **Cách nối trace với log:** correlation_id được đưa vào propagate_attributes(metadata={...}) trong run(). Cùng ID này có trong mọi log line. Filter trên Langfuse bằng metadata.correlation_id:req-xxxxxxxx để tìm đúng trace
- **Prompt name:** day13-chat
- **Version/label baseline:** version #1
- **Version/label candidate:** version #4
- **Trace ID của mỗi version:** với v1 → <trace-id-1>, với v4 → <trace-id-4>. Nếu chưa đổi version giữa 2 lần chạy, chỉ cần ghi trace ID của lần chạy hiện tại
- **Cách promote và rollback `production`:** production: Vào Langfuse UI → Prompt day13-chat → chọn version → click label icon → set production. Rollback: chọn version cũ hơn → set production lại. Evidence: evidence/09-prompt-versions.png, evidence/10-prompt-rollback.png

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** Xây bằng Streamlit (scripts/dashboard_app.py), đọc data/logs.jsonl, render đúng 6 panel theo config/dashboard.yaml: latency, traffic, errors, cost, tokens, quality. Time range 60 phút, refresh 30 giây, có threshold/SLO line. Evidence: evidence/11-dashboard-overview.png
- **SLO và lý do chọn:** SLO fast_successful_requests — p95 latency ≤ 3000ms, target 99.5% trong 28 ngày. Baseline thực đo p95 ≈ 1422ms, nên ngưỡng 3000ms cho ~2x headroom, đủ chịu spike mà không false-alarm
- **Cách tính error budget:** 0.5% × 40320 phút = 201.6 phút / 28 ngày (~3.36 giờ). Fast burn: budget cạn trong ~2 ngày (threshold multiplier 14.4x). Slow burn: ~5 ngày (6x)
- **Ba alert và runbook tương ứng:** (1) high_latency_p95 — p95 > 3000ms trong 10 phút, critical, owner @oncall-llmops; (2) high_error_rate — error rate > 2% trong 5 phút, critical, owner @oncall-llmops; (3) low_retrieval_success — tool_success < 90% trong 15 phút, warning, owner @team-rag. Cả 3 đều symptom-based, runbook chi tiết trong docs/alerts.md

## 7. Điều tra challenge

- **Challenge ID:** day13-k4-l3a-monitoring-llmops-v1
- **Khoảng thời gian điều tra:** 2026-09-29 15:25–15:28 UTC
- **Triệu chứng từ metrics:** Panel latency P95 ≈ 16300ms, cao hơn baseline ~100x; error rate = 0%; cost bình thường → không phải lỗi logic, chỉ là performance
- **Log line và correlation ID liên quan:** req-4ebfbdc1 (hoặc req-1834faa0), event response_sent, latency_ms: 16329, ttft_ms: 50, tool_name: retrieval, tool_success: true. Evidence: evidence/13-incident-log.png
- **Trace ID và span gây ảnh hưởng:** Trace 4202e0c17bc4a3f8a227812731cf2824. Span retrieval chiếm ~2.5s trong trace, llm-call chỉ ~0.15s → bottleneck ở retrieval. Evidence: evidence/14-incident-trace.png
- **Root cause:** Incident toggle rag_slow: true khiến retrieve() trong app/mock_rag.py sleep nhân tạo ~16 giây trước khi trả kết quả. Retrieval span bị block, kéo toàn bộ request chậm theo. tool_success: true xác nhận retrieval vẫn thành công, chỉ chậm
- **Fix action:** python scripts/inject_incident.py --scenario rag_slow --disable. Chạy lại load test để xác nhận latency về baseline ~160ms
- **Preventive measure:** (1) Alert high_latency_p95 p95 > 3000ms/10min; (2) Đặt timeout cứng 5s cho RAG call để tránh block toàn request; (3) Circuit breaker: nếu retrieval fail/chậm N lần liên tiếp → fallback keyword search; (4) Theo dõi error budget của SLO; (5) Health-check định kỳ cho vector store/RAG service

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** Chọn @observe decorator thay vì langfuse_client.start_as_current_observation(...) vì (a) mock client trong test chỉ implement get_prompt + update_current_span, (b) decorator không cần client method nào nên test pass, (c) SDK v4 không expose context-manager API ở module level
- **Một lỗi/blocker đã gặp:** AttributeError: module 'langfuse' has no attribute 'start_as_current_span' — SDK v4 đã remove API v3
- **Cách tìm nguyên nhân và xử lý:** Chạy pip show langfuse → xác nhận v4.15.6. Đọc traceback kỹ → thấy API bị gọi sai tầng. Thử start_as_current_observation → vẫn fail. Cuối cùng đọc test mock → hiểu test chỉ cần update_current_span, chuyển sang @observe
- **Cách hiểu luồng Metrics → Logs → Traces:** Metrics chỉ ra triệu chứng. Logs cho correlation ID của request bất thường + metric chi tiết. Traces cho span nào trong request đó chậm → khoanh vùng root cause
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** Prompt version cho phép thay đổi template không cần redeploy, token/cost đo hiệu quả kinh tế; SLO định nghĩa "tốt" và error budget, rollback là safety net khi deploy prompt mới làm chất lượng giảm
- **Điều quan trọng nhất đã học:** Correlation ID là sợi dây duy nhất nối Metrics ↔ Logs ↔ Traces. Không có nó, mỗi hệ thống là một ốc đảo không debug được
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:**

## 9. Checklist trước khi nộp

- [ ] Kết quả và evidence thuộc commit SHA cuối.
- [ ] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [ ] Incident evidence nối đúng metric → log → trace.
- [ ] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [ ] Repository chạy lại được theo README.
- [ ] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
