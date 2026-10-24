
async function loadEmails() {
    const container = document.querySelector("#messages-container");

    try {
        const response = await fetch("/api/emails", {
            headers: {
                "Accept": "application/json"
            },
            credentials: "same-origin"
        });

        const contentType = response.headers.get("content-type") || "";

        if (!contentType.includes("application/json")) {
            throw new Error(
                `Expected JSON but received HTML or another response. HTTP ${response.status}`
            );
        }

        const data = await response.json();

        if (response.status === 401) {
            window.location.href = "/login";
            return;
        }

        if (!response.ok) {
            throw new Error(data.error || `HTTP ${response.status}`);
        }

        console.log("Fetched emails:", data.emails);

        // Pass data.emails to your existing dashboard rendering function.
        renderEmails(data.emails);

    } catch (error) {
        console.error("Email loading error:", error);

        if (container) {
            container.textContent = error.message;
        }
    }
}
