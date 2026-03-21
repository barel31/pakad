addEventListener("fetch", function (event) {
  event.respondWith(handleRequest());
});

async function handleRequest() {
  var res = await fetch(
    "https://www.oref.org.il/WarningMessages/alert/alerts.json",
    {
      headers: {
        "Referer": "https://www.oref.org.il/",
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "he-IL,he;q=0.9",
      },
    }
  );
  var body = await res.text();
  return new Response(body, {
    status: res.status,
    headers: {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": "*",
    },
  });
}
