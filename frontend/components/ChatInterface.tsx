"use client";

import { useState } from "react";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

type ChatInterfaceProps = {
  jobId: string | null;
  disabled?: boolean;
};

export default function ChatInterface({ jobId, disabled }: ChatInterfaceProps) {
  const [history, setHistory] = useState<ChatMessage[]>([]);
  const [message, setMessage] = useState("");
  const [status, setStatus] = useState<string | null>(null);

  const sendMessage = async () => {
    if (!jobId || !message.trim()) {
      return;
    }

    const newMessage: ChatMessage = { role: "user", content: message.trim() };
    const nextHistory = [...history, newMessage];
    setHistory(nextHistory);
    setMessage("");
    setStatus("Thinking...");

    const response = await fetch("/api/proxy/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        job_id: jobId,
        message: newMessage.content,
        history: nextHistory,
      }),
    });

    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      setStatus(payload?.error?.message || "Chat failed.");
      return;
    }

    const data = await response.json();
    setHistory([...nextHistory, { role: "assistant", content: data.response }]);
    setStatus(null);
  };

  return (
    <div className="field">
      <div className="chat-window">
        {history.length === 0 ? (
          <span className="badge">No messages yet.</span>
        ) : (
          history.map((entry, index) => (
            <div key={index} className={`chat-bubble ${entry.role}`}>
              <strong>{entry.role === "user" ? "You" : "Assistant"}:</strong> {entry.content}
            </div>
          ))
        )}
      </div>
      <div className="inline-row">
        <input
          className="input"
          type="text"
          placeholder="Ask about dimensions, material, or notes..."
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          disabled={disabled}
        />
        <button className="button" onClick={sendMessage} disabled={disabled}>
          Send
        </button>
      </div>
      {status && <span className="badge">{status}</span>}
    </div>
  );
}
