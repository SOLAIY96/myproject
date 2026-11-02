
import { useEffect, useRef, useState } from "react";
import { apiRequest } from "./services/api";

function App() {
  const [username, setUsername] = useState(
    () => sessionStorage.getItem("username") || ""
  );
  const [password, setPassword] = useState("");
  const [accessToken, setAccessToken] = useState(
    () => sessionStorage.getItem("accessToken") || ""
  );
  const [refreshToken, setRefreshToken] = useState(
    () => sessionStorage.getItem("refreshToken") || ""
  );

  const [tasks, setTasks] = useState([]);
  const [newTaskTitle, setNewTaskTitle] = useState("");
  const [editingTaskId, setEditingTaskId] = useState(null);
  const [editingTaskTitle, setEditingTaskTitle] = useState("");

  const [selectedFile, setSelectedFile] = useState(null);
  const [attachments, setAttachments] = useState([]);
  const [uploading, setUploading] = useState(false);

  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  const fileInputRef = useRef(null);

  const [checkoutResult, setCheckoutResult] = useState(null);
  const [checkoutSessionId, setCheckoutSessionId] = useState("");

  const [checkoutLoading, setCheckoutLoading] = useState(false);

  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [notificationsLoading, setNotificationsLoading] = useState(false);

  function clearFeedback() {
    setError("");
    setMessage("");
  }

  // AUTHENTICATION

  async function handleLogin(event) {
    event.preventDefault();
    clearFeedback();
    setLoading(true);

    try {
      const data = await apiRequest("/token/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });

      setAccessToken(data.access);
      setRefreshToken(data.refresh);
      sessionStorage.setItem("username", username);
      sessionStorage.setItem("accessToken", data.access);
      sessionStorage.setItem("refreshToken", data.refresh);
      setPassword("");
      setTasks([]);
      setAttachments([]);
      setNotifications([]);
      setUnreadCount(0);
      setMessage("Login successful!");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function logout() {
    setAccessToken("");
    setRefreshToken("");
    setPassword("");
    setTasks([]);
    setAttachments([]);
    setNotifications([]);
    setUnreadCount(0);
    setSelectedFile(null);
    setNewTaskTitle("");
    setEditingTaskId(null);
    setEditingTaskTitle("");
    sessionStorage.removeItem("username");
    sessionStorage.removeItem("accessToken");
    sessionStorage.removeItem("refreshToken");

    setCheckoutResult(null);
    setCheckoutSessionId("");

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }

    clearFeedback();
    setMessage("Logged out successfully.");
  }

  async function refreshAccessToken() {
    try {
      const data = await apiRequest("/token/refresh/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh: refreshToken }),
      });

      setAccessToken(data.access);
      sessionStorage.setItem("accessToken", data.access);
      if (data.refresh) {
        setRefreshToken(data.refresh);
        sessionStorage.setItem("refreshToken", data.refresh);
      }

      return data.access;
    } catch {
      logout();
      setError("Your session expired. Please log in again.");
      return null;
    }
  }

  async function authenticatedRequest(path, options = {}) {
    if (!accessToken) {
      throw new Error("Please log in first.");
    }

    async function send(token) {
      const headers = new Headers(options.headers || {});
      headers.set("Authorization", `Bearer ${token}`);

      return apiRequest(path, { ...options, headers });
    }

    try {
      return await send(accessToken);
    } catch (err) {
      if (err.status !== 401) throw err;

      const token = await refreshAccessToken();

      if (!token) {
        throw new Error("Please log in again.");
      }

      return send(token);
    }
  }

  // PAYMENTS

  async function startCheckout() {
    clearFeedback();
    setCheckoutLoading(true);

    try {
      const data = await authenticatedRequest("/payments/checkout/", {
        method: "POST",
      });

      if (!data.checkout_url) {
        throw new Error("Django did not return a checkout URL.");
      }

      setMessage(`Order #${data.order_id} created. Redirecting to Stripe...`);

      window.location.assign(data.checkout_url);
    } catch (err) {
      setError(err.message || "Unable to start checkout.");
    } finally {
      setCheckoutLoading(false);
    }
  }

  async function checkCheckoutStatus(sessionId) {
  if (!sessionId) {
    setError("Missing Stripe Checkout session ID.");
    return;
  }

  clearFeedback();
  setPaymentsLoading(true);
  setCheckoutSessionId(sessionId);

  try {
    const data = await authenticatedRequest(
      `/payments/checkout/status/?session_id=${encodeURIComponent(sessionId)}`
    );

    setCheckoutResult(data);

    // Refresh the user's notifications from Django.
    await loadNotifications();

    const paymentStatus = String(data.status).toLowerCase();

    if (paymentStatus === "paid") {
      setMessage(
        `Payment confirmed! Order #${data.order_id} has been paid.`
      );
    } else if (paymentStatus === "pending") {
      setMessage(
        `Order #${data.order_id} is still pending. ` +
        "If you just paid, refresh the status shortly."
      );
      } else {
        setMessage(
          `Order #${data.order_id} status: ${data.status}.`
        );
      }
    } catch (err) {
      setError(err.message || "Unable to check payment status.");
    } finally {
      setPaymentsLoading(false);
    }
  }

  // NOTIFICATIONS

  async function loadNotifications() {
    clearFeedback();
    setNotificationsLoading(true);

    try {
      const [notificationData, countData] = await Promise.all([
        authenticatedRequest("/notifications/"),
        authenticatedRequest("/notifications/unread-count/"),
      ]);

      const results = Array.isArray(notificationData)
        ? notificationData
        : notificationData.results;

      if (!Array.isArray(results)) {
        throw new Error("Invalid notifications response from Django.");
      }

      setNotifications(results);
      setUnreadCount(countData.unread_count ?? 0);
    } catch (err) {
      setError(err.message || "Unable to load notifications.");
    } finally {
      setNotificationsLoading(false);
    }
  }

  async function markNotificationAsRead(notificationId) {
    clearFeedback();

    try {
      const updated = await authenticatedRequest(
        `/notifications/${notificationId}/`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ is_read: true }),
        }
      );

      setNotifications((current) =>
        current.map((notification) =>
          notification.id === notificationId
            ? { ...notification, ...updated }
            : notification
        )
      );

      // Refresh the server's count instead of guessing.
      const countData = await authenticatedRequest(
        "/notifications/unread-count/"
      );

      setUnreadCount(countData.unread_count ?? 0);
      setMessage("Notification marked as read.");
    } catch (err) {
      setError(err.message || "Unable to update notification.");
    }
  }

  // TASKS

  async function loadTasks() {
    clearFeedback();
    setLoading(true);

    try {
      const data = await authenticatedRequest("/tasks/");
      const results = Array.isArray(data) ? data : data.results;

      if (!Array.isArray(results)) {
        throw new Error("Invalid tasks response from Django.");
      }

      setTasks(results);
      setMessage("Tasks loaded successfully!");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function createTask(event) {
    event.preventDefault();
    clearFeedback();

    const title = newTaskTitle.trim();

    if (!title) {
      setError("Task title cannot be empty.");
      return;
    }

    try {
      const data = await authenticatedRequest("/tasks/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
      });

      setTasks((current) => [...current, data]);
      setNewTaskTitle("");
      setMessage("Task created successfully!");
    } catch (err) {
      setError(err.message);
    }
  }

  async function updateTask(taskId) {
    clearFeedback();

    const title = editingTaskTitle.trim();

    if (!title) {
      setError("Task title cannot be empty.");
      return;
    }

    try {
      const data = await authenticatedRequest(`/tasks/${taskId}/`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
      });

      setTasks((current) =>
        current.map((task) => task.id === taskId ? data : task)
      );

      setEditingTaskId(null);
      setEditingTaskTitle("");
      setMessage("Task updated successfully!");
    } catch (err) {
      setError(err.message);
    }
  }

  async function deleteTask(taskId) {
    clearFeedback();

    if (!window.confirm("Delete this task?")) return;

    try {
      await authenticatedRequest(`/tasks/${taskId}/`, {
        method: "DELETE",
      });

      setTasks((current) =>
        current.filter((task) => task.id !== taskId)
      );

      setMessage("Task deleted successfully!");
    } catch (err) {
      setError(err.message);
    }
  }

  // FILE ATTACHMENTS

  async function loadAttachments() {
    clearFeedback();
    setLoading(true);

    try {
      const data = await authenticatedRequest("/attachments/");
      const results = Array.isArray(data) ? data : data.results;

      if (!Array.isArray(results)) {
        throw new Error("Invalid attachments response from Django.");
      }

      setAttachments(results);
      setMessage("Attachments loaded successfully!");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function handleFileChange(event) {
    clearFeedback();

    const file = event.target.files?.[0] || null;

    if (!file) {
      setSelectedFile(null);
      return;
    }

    const allowedTypes = [
      "application/pdf",
      "image/jpeg",
      "image/png",
    ];

    if (!allowedTypes.includes(file.type)) {
      setError("Only PDF, JPEG, and PNG files are allowed.");
      setSelectedFile(null);
      event.target.value = "";
      return;
    }

    if (file.size > 5 * 1024 * 1024) {
      setError("File size cannot exceed 5 MB.");
      setSelectedFile(null);
      event.target.value = "";
      return;
    }

    setSelectedFile(file);
  }

  async function uploadAttachment(event) {
    event.preventDefault();
    clearFeedback();

    if (!selectedFile) {
      setError("Please select a file first.");
      return;
    }

    const formData = new FormData();
    formData.append("file", selectedFile);

    setUploading(true);

    try {
      const data = await authenticatedRequest("/attachments/", {
        method: "POST",
        body: formData,
      });

      setAttachments((current) => [data, ...current]);
      setSelectedFile(null);

      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }

      setMessage("File uploaded successfully!");
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  }

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const checkout = params.get("checkout");

    if (!checkout) return;

    if (checkout === "cancelled") {
      window.history.replaceState(
        {},
        document.title,
        window.location.pathname
      );

      setCheckoutResult(null);
      setCheckoutSessionId("");
      setMessage(
        "Checkout was cancelled. No payment confirmation was received."
      );
      return;
    }

    if (checkout !== "success") return;

    const sessionId = params.get("session_id");

    if (!sessionId) {
      window.history.replaceState(
        {},
        document.title,
        window.location.pathname
      );

      setError("Stripe returned without a Checkout session ID.");
      return;
    }

    // Wait until the user is authenticated before checking the order.
    // Keep the query string until then so login can trigger this effect again.
    if (!accessToken) {
      setMessage(
        "Please log in to check your payment status."
      );
      return;
    }

    window.history.replaceState(
      {},
      document.title,
      window.location.pathname
    );

    setCheckoutSessionId(sessionId);
    checkCheckoutStatus(sessionId);
  }, [accessToken]);

  // USER INTERFACE

  return (
    <main
      style={{
        maxWidth: "800px",
        margin: "30px auto",
        padding: "20px",
        fontFamily: "Arial, sans-serif",
      }}
    >
      <h1>My Django + React Project</h1>

      {error && (
        <p role="alert" style={{ color: "red" }}>
          ❌ {error}
        </p>
      )}

      {message && (
        <p role="status" style={{ color: "green" }}>
          ✅ {message}
        </p>
      )}

      {!accessToken ? (
        <section>
          <h2>Login</h2>

          <form onSubmit={handleLogin}>
            <div>
              <label htmlFor="username">Username</label>
              <br />
              <input
                id="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                required
              />
            </div>

            <br />

            <div>
              <label htmlFor="password">Password</label>
              <br />
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
              />
            </div>

            <br />

            <button type="submit" disabled={loading}>
              {loading ? "Logging in..." : "Login"}
            </button>
          </form>
        </section>
      ) : (
        <>
          <section>
            <h2>Account</h2>
            <p>Logged in as {username}</p>

            <button onClick={logout}>Logout</button>{" "}

            <button
              onClick={async () => {
                clearFeedback();
                const token = await refreshAccessToken();

                if (token) {
                  setMessage("Access token refreshed!");
                }
              }}
            >
              Refresh Token
            </button>
          </section>

          <hr />

          <section>
            <h2>Payments</h2>

            <p>
              Test purchase: <strong>USD 10.00</strong>
            </p>

            <p>
              Checkout runs through Stripe's hosted test checkout.
            </p>

            <button
              onClick={startCheckout}
              disabled={checkoutLoading}
            >
              {checkoutLoading
                ? "Creating checkout..."
                : "Pay with Stripe (Test Mode)"}
            </button>

            {checkoutResult && (
              <div
                style={{
                  marginTop: "20px",
                  padding: "15px",
                  border: "1px solid #ccc",
                  borderRadius: "8px",
                }}
              >
                <h3>Payment Result</h3>

                <p>
                  <strong>Order:</strong> #{checkoutResult.order_id}
                </p>

                <p>
                  <strong>Amount:</strong>{" "}
                  {checkoutResult.currency.toUpperCase()}{" "}
                  {checkoutResult.amount}
                </p>

                <p>
                  <strong>Status:</strong>{" "}
                  {String(checkoutResult.status).toUpperCase()}
                </p>

                <button
                  onClick={() => checkCheckoutStatus(checkoutSessionId)}
                  disabled={paymentsLoading || !checkoutSessionId}
                >
                  {paymentsLoading
                    ? "Checking..."
                    : "Refresh Payment Status"}
                </button>
              </div>
            )}
          </section>

          <hr />

          <section>
            <h2>
              Notifications
              {" "}
              <span>
                ({unreadCount} unread)
              </span>
            </h2>

            <button
              onClick={loadNotifications}
              disabled={notificationsLoading}
            >
              {notificationsLoading
                ? "Loading notifications..."
                : "Load Notifications"}
            </button>

            {notifications.length === 0 && !notificationsLoading && (
              <p>No notifications loaded. Click the button to check.</p>
            )}

            <ul>
              {notifications.map((notification) => (
                <li
                  key={notification.id}
                  style={{ marginBottom: "16px" }}
                >
                  <p>
                    <strong>
                      {notification.is_read ? "Read" : "Unread"}
                    </strong>
                    {" — "}
                    {notification.message}
                  </p>

                  {notification.created_at && (
                    <small>
                      {new Date(notification.created_at).toLocaleString()}
                    </small>
                  )}

                  {!notification.is_read && (
                    <div>
                      <button
                        onClick={() => markNotificationAsRead(notification.id)}
                      >
                        Mark as read
                      </button>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </section>

          <section>
            <h2>Tasks</h2>

            <form onSubmit={createTask}>
              <input
                value={newTaskTitle}
                onChange={(e) => setNewTaskTitle(e.target.value)}
                placeholder="Enter task title"
                required
              />
              {" "}
              <button type="submit">Create Task</button>
            </form>

            <br />

            <button onClick={loadTasks} disabled={loading}>
              {loading ? "Loading..." : "Load Tasks"}
            </button>

            <ul>
              {tasks.map((task) => (
                <li key={task.id} style={{ marginBottom: "12px" }}>
                  {editingTaskId === task.id ? (
                    <>
                      <input
                        value={editingTaskTitle}
                        onChange={(e) =>
                          setEditingTaskTitle(e.target.value)
                        }
                      />

                      <button onClick={() => updateTask(task.id)}>
                        Save
                      </button>{" "}

                      <button
                        onClick={() => {
                          setEditingTaskId(null);
                          setEditingTaskTitle("");
                        }}
                      >
                        Cancel
                      </button>
                    </>
                  ) : (
                    <>
                      {task.title}{" "}

                      <button
                        onClick={() => {
                          setEditingTaskId(task.id);
                          setEditingTaskTitle(task.title || "");
                        }}
                      >
                        Edit
                      </button>{" "}

                      <button onClick={() => deleteTask(task.id)}>
                        Delete
                      </button>
                    </>
                  )}
                </li>
              ))}
            </ul>
          </section>

          <hr />

          <section>
            <h2>File Attachments</h2>

            <form onSubmit={uploadAttachment}>
              <label htmlFor="attachment-file">
                Choose a PDF, JPEG, or PNG (maximum 5 MB)
              </label>
              <br />

              <input
                ref={fileInputRef}
                id="attachment-file"
                type="file"
                accept=".pdf,.jpg,.jpeg,.png"
                onChange={handleFileChange}
                disabled={uploading}
              />

              {selectedFile && (
                <p>
                  Selected: {selectedFile.name} (
                  {(selectedFile.size / 1024).toFixed(1)} KB)
                </p>
              )}

              <button
                type="submit"
                disabled={uploading || !selectedFile}
              >
                {uploading ? "Uploading..." : "Upload File"}
              </button>
            </form>

            <br />

            <button onClick={loadAttachments} disabled={loading}>
              Load Attachments
            </button>

            <ul>
              {attachments.map((attachment) => {
                const fileName = attachment.file
                  ? decodeURIComponent(
                      attachment.file.split("/").pop().split("?")[0]
                    )
                  : "Attachment";

                let fileUrl = null;

                try {
                  if (attachment.file) {
                    const base = new URL(`${API_URL}/`);
                    const url = new URL(attachment.file, base);

                    if (url.origin === base.origin) {
                      fileUrl = url.href;
                    }
                  }
                } catch {
                  fileUrl = null;
                }

                return (
                  <li
                    key={attachment.id}
                    style={{ marginBottom: "15px" }}
                  >
                    <strong>{fileName}</strong>
                    <br />

                    {attachment.created_at && (
                      <span>
                        Uploaded:{" "}
                        {new Date(
                          attachment.created_at
                        ).toLocaleString()}
                        <br />
                      </span>
                    )}

                    {fileUrl ? (
                      <a
                        href={fileUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        Open file
                      </a>
                    ) : (
                      <span>File URL unavailable</span>
                    )}
                  </li>
                );
              })}
            </ul>
          </section>
        </>
      )}
    </main>
  );
}

export default App;
