const BASE = "/api";

async function handle(response) {
  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
    try {
      const body = await response.json();
      if (body.detail) detail = body.detail;
    } catch {
      // response wasn't JSON — keep the generic message
    }
    throw new Error(detail);
  }
  return response.json();
}

export async function uploadDocument(file) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${BASE}/documents/upload`, {
    method: "POST",
    body: formData,
  });
  return handle(res);
}

export async function listDocuments() {
  const res = await fetch(`${BASE}/documents`);
  return handle(res);
}

export async function getDocument(id) {
  const res = await fetch(`${BASE}/documents/${id}`);
  return handle(res);
}

export async function reprocessDocument(id) {
  const res = await fetch(`${BASE}/documents/${id}/process`, { method: "POST" });
  return handle(res);
}

export async function semanticSearch(query, documentId, topK = 5) {
  const res = await fetch(`${BASE}/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, document_id: documentId ?? null, top_k: topK }),
  });
  return handle(res);
}

export async function askQuestion(question, documentId, topK = 5) {
  const res = await fetch(`${BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, document_id: documentId ?? null, top_k: topK }),
  });
  return handle(res);
}

export async function getHealth() {
  const res = await fetch(`${BASE}/health`);
  return handle(res);
}

// ---------- Phase 2: Research Projects ----------

export async function createProject(name, description) {
  const res = await fetch(`${BASE}/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, description: description || null }),
  });
  return handle(res);
}

export async function listProjects() {
  const res = await fetch(`${BASE}/projects`);
  return handle(res);
}

export async function getProject(projectId) {
  const res = await fetch(`${BASE}/projects/${projectId}`);
  return handle(res);
}

export async function updateProject(projectId, patch) {
  const res = await fetch(`${BASE}/projects/${projectId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  return handle(res);
}

export async function deleteProject(projectId) {
  const res = await fetch(`${BASE}/projects/${projectId}`, { method: "DELETE" });
  return handle(res);
}

export async function uploadPaperToProject(projectId, file) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${BASE}/projects/${projectId}/documents`, {
    method: "POST",
    body: formData,
  });
  return handle(res);
}

export async function listProjectDocuments(projectId) {
  const res = await fetch(`${BASE}/projects/${projectId}/documents`);
  return handle(res);
}

export async function removePaperFromProject(projectId, documentId) {
  const res = await fetch(`${BASE}/projects/${projectId}/documents/${documentId}`, {
    method: "DELETE",
  });
  return handle(res);
}

export async function askProjectQuestion(projectId, question, topK = 8) {
  const res = await fetch(`${BASE}/projects/${projectId}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, top_k: topK }),
  });
  return handle(res);
}

export async function getProjectChatHistory(projectId) {
  const res = await fetch(`${BASE}/projects/${projectId}/chat/history`);
  return handle(res);
}

export async function compareProjectPapers(projectId, documentIds) {
  const res = await fetch(`${BASE}/projects/${projectId}/compare`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document_ids: documentIds }),
  });
  return handle(res);
}

export async function getLiteratureMatrix(projectId, forceRefresh = false) {
  const res = await fetch(
    `${BASE}/projects/${projectId}/literature-matrix?force_refresh=${forceRefresh}`
  );
  return handle(res);
}

export async function runGapAnalysis(projectId, forceRefresh = false) {
  const res = await fetch(`${BASE}/projects/${projectId}/gap-analysis`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ force_refresh: forceRefresh }),
  });
  return handle(res);
}

export async function generateResearchQuestions(projectId, forceRefresh = false) {
  const res = await fetch(`${BASE}/projects/${projectId}/research-questions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ force_refresh: forceRefresh }),
  });
  return handle(res);
}

export async function getProjectAnalytics(projectId) {
  const res = await fetch(`${BASE}/projects/${projectId}/analytics`);
  return handle(res);
}

// ---------- Phase 3: Scientific Knowledge Extraction ----------

export async function analyzeDocument(documentId) {
  const res = await fetch(`${BASE}/documents/${documentId}/analyze`, { method: "POST" });
  return handle(res);
}

export async function getDocumentJobStatus(documentId, jobId) {
  const res = await fetch(`${BASE}/documents/${documentId}/jobs/${jobId}`);
  return handle(res);
}

export async function getPaperIntelligence(documentId) {
  const res = await fetch(`${BASE}/documents/${documentId}/intelligence`);
  return handle(res);
}

export async function analyzeProject(projectId, includeTopics = true) {
  const res = await fetch(`${BASE}/projects/${projectId}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ include_topics: includeTopics }),
  });
  return handle(res);
}

export async function getProjectJobStatus(projectId, jobId) {
  const res = await fetch(`${BASE}/projects/${projectId}/jobs/${jobId}`);
  return handle(res);
}

export async function getProjectKnowledge(projectId) {
  const res = await fetch(`${BASE}/projects/${projectId}/knowledge`);
  return handle(res);
}

export async function getProjectEntities(projectId) {
  const res = await fetch(`${BASE}/projects/${projectId}/entities`);
  return handle(res);
}

export async function getProjectEntityDetail(projectId, entityId) {
  const res = await fetch(`${BASE}/projects/${projectId}/entities/${entityId}`);
  return handle(res);
}

export async function getProjectTopics(projectId) {
  const res = await fetch(`${BASE}/projects/${projectId}/topics`);
  return handle(res);
}

export async function getProjectTopicDetail(projectId, topicId) {
  const res = await fetch(`${BASE}/projects/${projectId}/topics/${topicId}`);
  return handle(res);
}

export async function getMlInfo() {
  const res = await fetch(`${BASE}/system/ml-info`);
  return handle(res);
}

export async function searchLiterature(query, source = "all", limit = 10) {
  const params = new URLSearchParams({ query, source, limit: String(limit) });
  const res = await fetch(`${BASE}/discovery/search?${params.toString()}`);
  return handle(res);
}

export async function importDiscoveredPaper(projectId, paper) {
  const url = projectId
    ? `${BASE}/projects/${projectId}/discovery/import`
    : `${BASE}/documents/discovery/import`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(paper),
  });
  return handle(res);
}

export async function getDocumentCitation(documentId) {
  const res = await fetch(`${BASE}/documents/${documentId}/citation`);
  return handle(res);
}

export function getProjectBibtexUrl(projectId) {
  return `${BASE}/projects/${projectId}/export/bibtex`;
}

export function getProjectRisUrl(projectId) {
  return `${BASE}/projects/${projectId}/export/ris`;
}

export async function getAuthoringSection(projectId, sectionType) {
  const res = await fetch(`${BASE}/projects/${projectId}/authoring/${sectionType}`);
  return handle(res);
}

export async function generateAuthoringSection(projectId, sectionType, customInstructions, forceRefresh = false) {
  const res = await fetch(`${BASE}/projects/${projectId}/authoring/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      section_type: sectionType,
      custom_instructions: customInstructions || null,
      force_refresh: forceRefresh,
    }),
  });
  return handle(res);
}

