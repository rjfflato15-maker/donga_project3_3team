import React from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App.jsx";
import { StoryPreview } from "./StoryPreview.jsx";
import "./styles.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    {new URLSearchParams(location.search).has('story') ? <StoryPreview /> : <App />}
  </React.StrictMode>,
);
