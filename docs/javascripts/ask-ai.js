/* Floating “Ask AI” — opens Perplexity with repo + docs context (no FlightDeck servers). */
(function () {
  var url =
    "https://www.perplexity.ai/search?q=" +
    encodeURIComponent(
      "FlightDeck: AI agent release governance (CLI, SQLite ledger, policy gates, diff, promote). Official docs site https://flightdeckdev.github.io/flightdeck/ and source https://github.com/flightdeckdev/flightdeck — answer using those when possible."
    );

  function addButton() {
    if (document.getElementById("fd-floating-ask-ai")) {
      return;
    }
    var a = document.createElement("a");
    a.id = "fd-floating-ask-ai";
    a.href = url;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.textContent = "Ask AI";
    a.setAttribute(
      "aria-label",
      "Ask AI about FlightDeck in Perplexity (new tab)"
    );
    document.body.appendChild(a);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", addButton);
  } else {
    addButton();
  }
})();
