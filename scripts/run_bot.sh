#!/usr/bin/env bash
# ==============================================================================
# اسکریپت سرپرست اجرای ۲۴/۷ ربات تلگرام داخل GitHub Actions
#
# ۱) اجرای خودکار و پیوسته ربات؛ در صورت کرش بلافاصله دوباره بالا می‌آید.
# ۲) قبل از رسیدن به سقف ۶ ساعته‌ی GitHub Actions، خودش تمیز خارج می‌شود تا
#    Job بعدی (که در صف concurrency منتظر است) بدون وقفه جایش را بگیرد.
# ۳) در صورت دریافت کامیت جدید روی main، ربات فوراً خارج می‌شود تا نسخه جدید
#    با تغییرات تازه بالا بیاید.
# ==============================================================================

set -u

BOT_RUN_MINUTES="${BOT_RUN_MINUTES:-320}"
BOT_JOB_MINUTES="${BOT_JOB_MINUTES:-335}"
CHECK_UPDATES="${CHECK_UPDATES:-1}"

job_deadline=$(( $(date +%s) + BOT_JOB_MINUTES * 60 ))
attempt=0
backoff=5

log() { printf '%s [supervisor] %s\n' "$(date -u +%H:%M:%S)" "$*"; }

remote_changed() {
  [ "$CHECK_UPDATES" = "1" ] || return 1
  [ -n "${GITHUB_SHA:-}" ] || return 1
  [ "${GITHUB_REF_NAME:-}" = "main" ] || return 1
  local remote
  remote=$(timeout 30 git ls-remote origin refs/heads/main 2>/dev/null | cut -f1)
  [ -n "$remote" ] && [ "$remote" != "$GITHUB_SHA" ]
}

while :; do
  now=$(date +%s)
  remaining=$(( job_deadline - now ))
  if [ "$remaining" -lt 120 ]; then
    log "سهمیه‌ی زمانی این Job به پایان رسید؛ خروج تمیز جهت تحویل به اجرای بعدی."
    exit 0
  fi

  run_minutes=$(( remaining / 60 ))
  [ "$run_minutes" -gt "$BOT_RUN_MINUTES" ] && run_minutes=$BOT_RUN_MINUTES

  if remote_changed; then
    log "کامیت جدید روی شاخه main شناسایی شد؛ خروج تمیز برای اعمال نسخه جدید."
    exit 0
  fi

  attempt=$(( attempt + 1 ))
  log "شروع تلاش #$attempt — ربات به مدت $run_minutes دقیقه اجرا می‌شود."

  RUN_DURATION_MINUTES="$run_minutes" python bot.py
  code=$?

  if [ "$code" -eq 0 ]; then
    log "ربات به صورت تمیز خارج شد (کد ۰)."
    if [ $(( $(date +%s) + 120 )) -ge "$job_deadline" ]; then
      log "پایان بازه زمانی Job؛ خروج موفق."
      exit 0
    fi
    sleep 2
    continue
  fi

  log "ربات با کد $code خارج شد؛ تلاش مجدد بعد از $backoff ثانیه..."
  sleep "$backoff"
  backoff=$(( backoff * 2 ))
  [ "$backoff" -gt 120 ] && backoff=120
done
