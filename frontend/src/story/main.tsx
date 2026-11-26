import React from "react";
import { createRoot } from "react-dom/client";
import StoryPage from "./StoryPage";

const el = document.getElementById("story-root");
if (!el) throw new Error("Elemento #story-root não encontrado.");
createRoot(el).render(<React.StrictMode><StoryPage/></React.StrictMode>);