const visitorKey = localStorage.getItem("gis_visitor_id") || crypto.randomUUID();
localStorage.setItem("gis_visitor_id", visitorKey);

const sessionKey = sessionStorage.getItem("gis_session_id") || crypto.randomUUID();
sessionStorage.setItem("gis_session_id", sessionKey);

export function event(eventName, properties = {}) {
  return {
    event_id: crypto.randomUUID(),
    event_name: eventName,
    event_version: 1,
    occurred_at: new Date().toISOString(),
    page_path: window.location.pathname,
    properties,
  };
}

export async function send(events) {
  return fetch("/api/telemetry", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      tenant_key: "vahomemath",
      site_key: "vahomemath",
      session_key: sessionKey,
      anonymous_visitor_key: visitorKey,
      events,
    }),
  });
}

// Examples:
// send([event("page_view", { page_title: document.title })]);
// const runKey = crypto.randomUUID();
// send([event("calculator_start", {
//   calculator_run_key: runKey, calculator_type: "va_loan",
//   input_schema_version: "va_loan:v1", home_price_bucket: "350k_400k"
// })]);
// send([event("calculator_complete", {
//   calculator_run_key: runKey, calculator_type: "va_loan",
//   result_schema_version: "va_loan_result:v1", monthly_payment_bucket: "2k_2250"
// })]);
// send([event("cta_click", { cta_id: "apply", cta_location: "results" })]);
// send([event("lead_form_complete", { form_id: "partner-lead", calculator_run_key: runKey })]);
