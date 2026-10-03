/**
 * VisualKnowledgeGraph.jsx
 * Interactive, data-driven research knowledge graph for Research Nexus.
 * Built with @xyflow/react — dynamically visualizes papers, authors, topics,
 * models, algorithms, datasets, methodologies, metrics, concepts, findings,
 * research questions, and research gaps extracted from actual literature data.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  MarkerType,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { getProjectGraph, queryProjectGraph, analyzeProject } from "../../../services/api.js";

// ─── Node type styles & icons ──────────────────────────────────────────────────
const NODE_STYLES = {
  paper:     { bg: "#0d4022", border: "#15803d", text: "#dcfce7", icon: "📄", label: "Paper" },
  author:    { bg: "#1e3a8a", border: "#3b82f6", text: "#dbeafe", icon: "👤", label: "Author" },
  topic:     { bg: "#4c1d95", border: "#8b5cf6", text: "#ede9fe", icon: "🔬", label: "Topic" },
  model:     { bg: "#881337", border: "#f43f5e", text: "#ffe4e6", icon: "🤖", label: "Model" },
  algorithm: { bg: "#0f766e", border: "#14b8a6", text: "#ccfbf1", icon: "🧮", label: "Algorithm" },
  dataset:   { bg: "#78350f", border: "#f59e0b", text: "#fef3c7", icon: "📊", label: "Dataset" },
  method:    { bg: "#134e4a", border: "#10b981", text: "#d1fae5", icon: "⚙️", label: "Method" },
  metric:    { bg: "#312e81", border: "#6366f1", text: "#e0e7ff", icon: "📏", label: "Metric" },
  domain:    { bg: "#713f12", border: "#eab308", text: "#fef08a", icon: "🌐", label: "Domain" },
  task:      { bg: "#14532d", border: "#22c55e", text: "#bbf7d0", icon: "✅", label: "Task" },
  concept:   { bg: "#1e293b", border: "#64748b", text: "#e2e8f0", icon: "💡", label: "Concept" },
  gap:       { bg: "#7c2d12", border: "#ea580c", text: "#ffedd5", icon: "⚠️", label: "Research Gap" },
  finding:   { bg: "#0c4a6e", border: "#0ea5e9", text: "#e0f2fe", icon: "🔍", label: "Finding" },
  question:  { bg: "#581c87", border: "#a855f7", text: "#f3e8ff", icon: "❓", label: "Question" },
};

const EDGE_COLOURS = {
  written_by:     "#3b82f6",
  studies:        "#8b5cf6",
  discusses:      "#64748b",
  uses:           "#10b981",
  proposes:       "#f43f5e",
  evaluates_on:   "#f59e0b",
  reports:        "#0ea5e9",
  has_limitation: "#ea580c",
  addresses:      "#a855f7",
  related_to:     "#94a3b8",
  extends:        "#14b8a6",
};

// ─── Custom Node Renderer ─────────────────────────────────────────────────────
function ResearchNode({ data, selected }) {
  const style = NODE_STYLES[data.node_type] || NODE_STYLES.concept;

  return (
    <div
      style={{
        background: style.bg,
        border: `2px solid ${selected ? "#38bdf8" : style.border}`,
        borderRadius: 8,
        padding: "8px 12px",
        minWidth: 110,
        maxWidth: 220,
        boxShadow: selected
          ? `0 0 0 3px #38bdf866, 0 8px 24px rgba(0,0,0,0.6)`
          : "0 2px 8px rgba(0,0,0,0.45)",
        transition: "all 0.15s ease",
        cursor: "pointer",
        position: "relative",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 4, marginBottom: 4 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
          <span style={{ fontSize: 13 }}>{style.icon}</span>
          <span
            style={{
              fontSize: 9,
              fontFamily: "monospace",
              textTransform: "uppercase",
              color: style.text + "cc",
              letterSpacing: 0.8,
              fontWeight: 600,
            }}
          >
            {style.label || data.node_type}
          </span>
        </div>
        {data.paper_count > 1 && (
          <span
            style={{
              background: style.border,
              color: style.text,
              borderRadius: 8,
              padding: "1px 5px",
              fontSize: 9,
              fontFamily: "monospace",
              fontWeight: 700,
            }}
            title={`Appears across ${data.paper_count} papers`}
          >
            {data.paper_count}P
          </span>
        )}
      </div>
      <div
        style={{
          fontSize: 12,
          fontWeight: 600,
          color: style.text,
          lineHeight: 1.3,
          wordBreak: "break-word",
        }}
      >
        {data.label}
      </div>
      {data.publication_year && (
        <span
          style={{
            display: "inline-block",
            marginTop: 4,
            fontSize: 9,
            fontFamily: "monospace",
            color: "#94a3b8",
          }}
        >
          {data.publication_year}
        </span>
      )}
    </div>
  );
}

const nodeTypes = { research: ResearchNode };

// ─── Inner Graph Canvas (Has access to useReactFlow) ───────────────────────────
function GraphCanvas({
  projectId,
  indexedDocuments,
  onNavigate,
}) {
  const reactFlow = useReactFlow();

  const [graphData, setGraphData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [error, setError] = useState(null);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  const [activeFilters, setActiveFilters] = useState(new Set(["all"]));
  const [searchQuery, setSearchQuery] = useState("");
  const [highlightedIds, setHighlightedIds] = useState(new Set());
  const [selectedNode, setSelectedNode] = useState(null);
  const [selectedEdge, setSelectedEdge] = useState(null);

  const [aiQuery, setAiQuery] = useState("");
  const [aiAnswer, setAiAnswer] = useState(null);
  const [aiLoading, setAiLoading] = useState(false);

  // ── Load graph data ──────────────────────────────────────────────────────────
  const loadGraph = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    setError(null);
    setSelectedNode(null);
    setSelectedEdge(null);
    setHighlightedIds(new Set());
    try {
      const data = await getProjectGraph(projectId);
      setGraphData(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadGraph();
  }, [loadGraph]);

  // ── Handle 1-click Extraction from Empty State ───────────────────────────────
  async function handleTriggerExtraction() {
    setExtracting(true);
    try {
      await analyzeProject(projectId, true);
      // Poll multiple times for background extraction progress
      setTimeout(loadGraph, 4000);
      setTimeout(loadGraph, 10000);
      setTimeout(() => {
        loadGraph();
        setExtracting(false);
      }, 18000);
    } catch (err) {
      setError(err.message);
      setExtracting(false);
    }
  }

  // ── Convert graph data to React Flow nodes/edges ─────────────────────────────
  const buildFlowElements = useCallback(
    (data, filters, search, highlighted) => {
      if (!data?.nodes?.length) return { rfNodes: [], rfEdges: [] };

      const showAll = filters.has("all");
      const searchLow = search.toLowerCase().trim();

      const visibleNodeIds = new Set(
        data.nodes
          .filter((n) => {
            if (!showAll && !filters.has(n.type)) return false;
            if (searchLow && !n.label.toLowerCase().includes(searchLow)) return false;
            return true;
          })
          .map((n) => n.id)
      );

      const rfNodes = data.nodes
        .filter((n) => visibleNodeIds.has(n.id))
        .map((n) => {
          const isHighlighted = highlighted.size > 0 && highlighted.has(n.id);
          const isDimmed = highlighted.size > 0 && !highlighted.has(n.id);
          return {
            id: n.id,
            type: "research",
            position: n.position,
            data: { ...n.data, node_type: n.type, label: n.label },
            style: {
              opacity: isDimmed ? 0.22 : 1,
              transform: isHighlighted ? "scale(1.06)" : "scale(1)",
              zIndex: isHighlighted ? 100 : 1,
            },
          };
        });

      const rfEdges = data.edges
        .filter((e) => visibleNodeIds.has(e.source) && visibleNodeIds.has(e.target))
        .map((e) => {
          const isConnected = highlighted.has(e.source) || highlighted.has(e.target);
          return {
            id: e.id,
            source: e.source,
            target: e.target,
            label: e.label,
            labelStyle: { fontSize: 9, fill: "#94a3b8", fontFamily: "monospace" },
            labelBgStyle: { fill: "#0f172a", fillOpacity: 0.8 },
            style: {
              stroke: EDGE_COLOURS[e.predicate] || "#64748b",
              strokeWidth: isConnected ? 2.5 : 1,
              opacity: highlighted.size > 0 && !isConnected ? 0.12 : 0.75,
            },
            markerEnd: {
              type: MarkerType.ArrowClosed,
              width: 8,
              height: 8,
              color: EDGE_COLOURS[e.predicate] || "#64748b",
            },
            animated: isConnected,
            data: e.data,
          };
        });

      return { rfNodes, rfEdges };
    },
    []
  );

  useEffect(() => {
    if (!graphData) return;
    const { rfNodes, rfEdges } = buildFlowElements(
      graphData,
      activeFilters,
      searchQuery,
      highlightedIds
    );
    setNodes(rfNodes);
    setEdges(rfEdges);
  }, [graphData, activeFilters, searchQuery, highlightedIds, buildFlowElements, setNodes, setEdges]);

  // ── Filter toggle ────────────────────────────────────────────────────────────
  function toggleFilter(type) {
    setActiveFilters((prev) => {
      const next = new Set(prev);
      if (type === "all") return new Set(["all"]);
      next.delete("all");
      if (next.has(type)) {
        next.delete(type);
        if (next.size === 0) next.add("all");
      } else {
        next.add(type);
      }
      return next;
    });
    setHighlightedIds(new Set());
    setSelectedNode(null);
    setSelectedEdge(null);
  }

  // ── Search handler with auto-centering ────────────────────────────────────────
  function handleSearch(e) {
    const q = e.target.value;
    setSearchQuery(q);
    setSelectedNode(null);
    setSelectedEdge(null);

    if (q.trim() && graphData?.nodes) {
      const matches = graphData.nodes.filter((n) =>
        n.label.toLowerCase().includes(q.toLowerCase())
      );
      const matchIds = new Set(matches.map((n) => n.id));
      const neighborIds = new Set(matchIds);

      graphData.edges.forEach((edge) => {
        if (matchIds.has(edge.source)) neighborIds.add(edge.target);
        if (matchIds.has(edge.target)) neighborIds.add(edge.source);
      });
      setHighlightedIds(neighborIds);

      if (matches.length === 1 && matches[0].position) {
        reactFlow.setCenter(matches[0].position.x, matches[0].position.y, {
          duration: 400,
          zoom: 1.2,
        });
      }
    } else {
      setHighlightedIds(new Set());
    }
  }

  // ── Node click ───────────────────────────────────────────────────────────────
  const handleNodeClick = useCallback(
    (_, node) => {
      setSelectedNode(node);
      setSelectedEdge(null);
      const connected = new Set([node.id]);
      if (graphData?.edges) {
        graphData.edges.forEach((e) => {
          if (e.source === node.id) connected.add(e.target);
          if (e.target === node.id) connected.add(e.source);
        });
      }
      setHighlightedIds(connected);
    },
    [graphData]
  );

  // ── Edge click ───────────────────────────────────────────────────────────────
  const handleEdgeClick = useCallback(
    (_, edge) => {
      setSelectedEdge(edge);
      setSelectedNode(null);
      setHighlightedIds(new Set([edge.source, edge.target]));
    },
    []
  );

  function clearSelection() {
    setSelectedNode(null);
    setSelectedEdge(null);
    setHighlightedIds(new Set());
    setSearchQuery("");
  }

  // ── AI Graph Query ───────────────────────────────────────────────────────────
  async function handleAiQuery(e) {
    e?.preventDefault();
    if (!aiQuery.trim()) return;
    setAiLoading(true);
    setAiAnswer(null);
    try {
      const focused = selectedNode ? [selectedNode.id] : [];
      const res = await queryProjectGraph(projectId, aiQuery, focused);
      setAiAnswer(res);
      if (res.relevant_nodes?.length > 0) {
        setHighlightedIds(new Set(res.relevant_nodes));
      }
    } catch (err) {
      setAiAnswer({ question: aiQuery, answer: `Error: ${err.message}`, relevant_nodes: [] });
    } finally {
      setAiLoading(false);
    }
  }

  // ── Connected papers for selected node ───────────────────────────────────────
  const connectedPapers = useMemo(() => {
    if (!selectedNode || !graphData) return [];
    const connected = [];
    graphData.edges.forEach((e) => {
      const otherId =
        e.source === selectedNode.id
          ? e.target
          : e.target === selectedNode.id
          ? e.source
          : null;
      if (otherId) {
        const other = graphData.nodes.find((n) => n.id === otherId && n.type === "paper");
        if (other) connected.push({ ...other, via: e.label });
      }
    });
    return connected;
  }, [selectedNode, graphData]);

  // ── Guard states ─────────────────────────────────────────────────────────────
  const hasIndexed = Array.isArray(indexedDocuments) && indexedDocuments.length > 0;

  if (!hasIndexed) {
    return (
      <div
        style={{
          display: "flex",
          height: "100%",
          alignItems: "center",
          justifyContent: "center",
          padding: "2rem",
          textAlign: "center",
          background: "#090d16",
        }}
      >
        <div style={{ maxWidth: 440 }}>
          <p style={{ fontSize: 48, marginBottom: 12 }}>🕸️</p>
          <p style={{ fontSize: 16, fontWeight: 700, color: "#f1f5f9", marginBottom: 6 }}>
            No indexed papers yet
          </p>
          <p style={{ fontSize: 13, color: "#94a3b8", lineHeight: 1.5, marginBottom: 16 }}>
            Add or import research papers in the Literature Discovery or Papers tab to begin generating your research knowledge graph.
          </p>
          <button
            onClick={() => onNavigate?.("discovery")}
            style={{
              background: "#166534",
              color: "#dcfce7",
              border: "1px solid #22c55e",
              borderRadius: 6,
              padding: "8px 18px",
              fontFamily: "monospace",
              fontSize: 12,
              cursor: "pointer",
            }}
          >
            Discover Papers →
          </button>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div
        style={{
          display: "flex",
          height: "100%",
          alignItems: "center",
          justifyContent: "center",
          background: "#090d16",
        }}
      >
        <div style={{ textAlign: "center" }}>
          <p style={{ fontSize: 44 }}>🕸️</p>
          <p
            style={{
              marginTop: 12,
              fontFamily: "monospace",
              fontSize: 11,
              textTransform: "uppercase",
              letterSpacing: 2,
              color: "#38bdf8",
            }}
          >
            Generating Research Knowledge Graph…
          </p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div
        style={{
          display: "flex",
          height: "100%",
          alignItems: "center",
          justifyContent: "center",
          background: "#090d16",
          padding: "2rem",
        }}
      >
        <div
          style={{
            borderRadius: 8,
            border: "1px solid #991b1b",
            background: "#1e1114",
            padding: "1.5rem",
            textAlign: "center",
            maxWidth: 420,
          }}
        >
          <p style={{ fontWeight: 600, color: "#f87171" }}>Failed to load knowledge graph</p>
          <p style={{ fontSize: 12, color: "#fca5a5", marginTop: 6 }}>{error}</p>
          <button
            onClick={loadGraph}
            style={{
              marginTop: 14,
              background: "#991b1b",
              color: "#fee2e2",
              border: "none",
              borderRadius: 6,
              padding: "6px 16px",
              fontSize: 12,
              cursor: "pointer",
            }}
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  const stats = graphData?.stats || {};
  const isEmpty = !graphData?.nodes?.length;
  const availableNodeTypes = Object.keys(stats.node_types || {});

  return (
    <div style={{ display: "flex", height: "100%", flexDirection: "column", background: "#090d16" }}>
      {/* ── Toolbar: Stats, Controls, Search ───────────────────────────────── */}
      <div
        style={{
          display: "flex",
          flexShrink: 0,
          flexWrap: "wrap",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 10,
          borderBottom: "1px solid #1e293b",
          background: "#0f172a",
          padding: "8px 16px",
        }}
      >
        {/* Left: Counts and fit screen */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <span style={{ fontFamily: "monospace", fontSize: 11, color: "#94a3b8" }}>
            <span style={{ color: "#38bdf8", fontWeight: 700 }}>{stats.total_nodes ?? 0}</span> nodes
            {" · "}
            <span style={{ color: "#38bdf8", fontWeight: 700 }}>{stats.total_edges ?? 0}</span> edges
          </span>

          <button
            onClick={() => reactFlow.fitView({ duration: 400, padding: 0.15 })}
            style={{
              borderRadius: 4,
              border: "1px solid #334155",
              background: "#1e293b",
              padding: "3px 8px",
              fontFamily: "monospace",
              fontSize: 10,
              textTransform: "uppercase",
              color: "#cbd5e1",
              cursor: "pointer",
            }}
            title="Fit graph into screen"
          >
            🎯 Fit Screen
          </button>

          <button
            onClick={() => reactFlow.zoomIn({ duration: 300 })}
            style={{
              borderRadius: 4,
              border: "1px solid #334155",
              background: "#1e293b",
              padding: "3px 8px",
              fontFamily: "monospace",
              fontSize: 10,
              color: "#cbd5e1",
              cursor: "pointer",
            }}
            title="Zoom In"
          >
            +
          </button>
          <button
            onClick={() => reactFlow.zoomOut({ duration: 300 })}
            style={{
              borderRadius: 4,
              border: "1px solid #334155",
              background: "#1e293b",
              padding: "3px 8px",
              fontFamily: "monospace",
              fontSize: 10,
              color: "#cbd5e1",
              cursor: "pointer",
            }}
            title="Zoom Out"
          >
            -
          </button>
        </div>

        {/* Right: Search & Refresh */}
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{ position: "relative" }}>
            <input
              type="text"
              value={searchQuery}
              onChange={handleSearch}
              placeholder="Search graph entities…"
              style={{
                width: 220,
                borderRadius: 6,
                border: "1px solid #334155",
                background: "#090d16",
                padding: "5px 28px 5px 12px",
                fontFamily: "monospace",
                fontSize: 11,
                color: "#e2e8f0",
                outline: "none",
              }}
            />
            {searchQuery && (
              <button
                onClick={() => {
                  setSearchQuery("");
                  setHighlightedIds(new Set());
                }}
                style={{
                  position: "absolute",
                  right: 8,
                  top: "50%",
                  transform: "translateY(-50%)",
                  background: "none",
                  border: "none",
                  color: "#94a3b8",
                  cursor: "pointer",
                  fontSize: 14,
                }}
              >
                ×
              </button>
            )}
          </div>

          {(selectedNode || selectedEdge || highlightedIds.size > 0 || searchQuery) && (
            <button
              onClick={clearSelection}
              style={{
                borderRadius: 6,
                border: "1px solid #334155",
                background: "#1e293b",
                padding: "5px 10px",
                fontFamily: "monospace",
                fontSize: 10,
                color: "#94a3b8",
                cursor: "pointer",
              }}
            >
              Clear Focus
            </button>
          )}

          <button
            onClick={loadGraph}
            style={{
              borderRadius: 6,
              border: "1px solid #334155",
              background: "#1e293b",
              padding: "5px 12px",
              fontFamily: "monospace",
              fontSize: 11,
              textTransform: "uppercase",
              color: "#cbd5e1",
              cursor: "pointer",
            }}
          >
            ↺ Refresh
          </button>
        </div>
      </div>

      {/* ── Filter Pills Bar ────────────────────────────────────────────────── */}
      <div
        style={{
          display: "flex",
          flexShrink: 0,
          flexWrap: "wrap",
          alignItems: "center",
          gap: 6,
          borderBottom: "1px solid #1e293b",
          background: "#0b1222",
          padding: "6px 16px",
        }}
      >
        <span style={{ fontSize: 10, fontFamily: "monospace", color: "#64748b", marginRight: 4 }}>
          FILTER:
        </span>
        <button
          onClick={() => toggleFilter("all")}
          style={{
            borderRadius: 4,
            padding: "3px 8px",
            fontFamily: "monospace",
            fontSize: 10,
            textTransform: "uppercase",
            cursor: "pointer",
            border: "1px solid",
            background: activeFilters.has("all") ? "#38bdf8" : "#1e293b",
            color: activeFilters.has("all") ? "#0f172a" : "#94a3b8",
            borderColor: activeFilters.has("all") ? "#38bdf8" : "#334155",
            fontWeight: activeFilters.has("all") ? 700 : 400,
          }}
        >
          All ({stats.total_nodes ?? 0})
        </button>

        {availableNodeTypes.map((type) => {
          const s = NODE_STYLES[type] || NODE_STYLES.concept;
          const isActive = activeFilters.has(type);
          const count = stats.node_types[type];
          return (
            <button
              key={type}
              onClick={() => toggleFilter(type)}
              style={{
                borderRadius: 4,
                padding: "3px 8px",
                fontFamily: "monospace",
                fontSize: 10,
                textTransform: "uppercase",
                cursor: "pointer",
                border: "1px solid",
                background: isActive ? s.bg : "#1e293b",
                color: isActive ? s.text : "#94a3b8",
                borderColor: isActive ? s.border : "#334155",
                fontWeight: isActive ? 600 : 400,
              }}
            >
              {s.icon} {s.label || type} ({count})
            </button>
          );
        })}
      </div>

      {/* ── Main Canvas & Inspector Area ───────────────────────────────────── */}
      <div style={{ display: "flex", minHeight: 0, flex: 1 }}>
        {/* React Flow Canvas */}
        <div style={{ flex: 1, minWidth: 0, position: "relative" }}>
          {isEmpty ? (
            <div
              style={{
                display: "flex",
                height: "100%",
                alignItems: "center",
                justifyContent: "center",
                textAlign: "center",
                padding: "2rem",
              }}
            >
              <div style={{ maxWidth: 440 }}>
                <p style={{ fontSize: 44, marginBottom: 8 }}>🕸️</p>
                <p style={{ fontSize: 16, fontWeight: 700, color: "#f1f5f9", marginBottom: 6 }}>
                  Knowledge Graph Ready for Extraction
                </p>
                <p style={{ fontSize: 13, color: "#94a3b8", lineHeight: 1.5, marginBottom: 18 }}>
                  Your papers are indexed. Run scientific extraction to parse models, datasets, methodologies, findings, and research gaps into your graph.
                </p>
                <button
                  onClick={handleTriggerExtraction}
                  disabled={extracting}
                  style={{
                    background: extracting ? "#1e293b" : "#166534",
                    color: "#dcfce7",
                    border: "1px solid #22c55e",
                    borderRadius: 6,
                    padding: "10px 20px",
                    fontFamily: "monospace",
                    fontSize: 12,
                    fontWeight: 600,
                    cursor: extracting ? "not-allowed" : "pointer",
                  }}
                >
                  {extracting ? "Extracting Entities & Graph… ⏳" : "⚡ Extract Entities & Build Graph"}
                </button>
              </div>
            </div>
          ) : (
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onNodeClick={handleNodeClick}
              onEdgeClick={handleEdgeClick}
              onPaneClick={clearSelection}
              nodeTypes={nodeTypes}
              fitView
              fitViewOptions={{ padding: 0.15 }}
              minZoom={0.05}
              maxZoom={3}
              colorMode="dark"
              proOptions={{ hideAttribution: true }}
            >
              <Background color="#1e293b" gap={24} size={0.7} />
              <Controls style={{ background: "#0f172a", border: "1px solid #334155" }} />
              <MiniMap
                style={{ background: "#0f172a", border: "1px solid #1e293b" }}
                nodeColor={(n) => NODE_STYLES[n.data?.node_type]?.border || "#64748b"}
                maskColor="#090d16cc"
              />
            </ReactFlow>
          )}
        </div>

        {/* ── Right Side Panel: Inspector & AI ─────────────────────────────── */}
        <div
          style={{
            display: "flex",
            width: 320,
            flexShrink: 0,
            flexDirection: "column",
            borderLeft: "1px solid #1e293b",
            background: "#0c1322",
            overflow: "hidden",
          }}
        >
          {/* Details Section */}
          <div
            style={{
              maxHeight: "58%",
              overflowY: "auto",
              borderBottom: "1px solid #1e293b",
            }}
          >
            {selectedEdge ? (
              <EdgeDetailPanel
                edge={selectedEdge}
                onSelectSource={() => {
                  const s = graphData?.nodes?.find((n) => n.id === selectedEdge.source);
                  if (s) handleNodeClick(null, s);
                }}
                onSelectTarget={() => {
                  const t = graphData?.nodes?.find((n) => n.id === selectedEdge.target);
                  if (t) handleNodeClick(null, t);
                }}
                onClear={clearSelection}
              />
            ) : selectedNode ? (
              <NodeDetailPanel
                node={selectedNode}
                connectedPapers={connectedPapers}
                onNavigate={onNavigate}
                onSelectRelated={(relatedLabel) => {
                  const match = graphData?.nodes?.find(
                    (n) => n.label.toLowerCase() === relatedLabel.toLowerCase()
                  );
                  if (match) handleNodeClick(null, match);
                }}
              />
            ) : (
              <div style={{ padding: "20px 16px", textAlign: "center" }}>
                <p style={{ fontSize: 28, marginBottom: 6 }}>🔍</p>
                <p style={{ fontSize: 13, fontWeight: 600, color: "#cbd5e1" }}>
                  Knowledge Graph Explorer
                </p>
                <p style={{ fontSize: 11, color: "#64748b", marginTop: 4, lineHeight: 1.4 }}>
                  Click any node or relationship edge in the graph to inspect detailed scientific evidence.
                </p>
              </div>
            )}
          </div>

          {/* AI Graph Assistant Section */}
          <div style={{ display: "flex", flex: 1, flexDirection: "column", minHeight: 0 }}>
            <div style={{ borderBottom: "1px solid #1e293b", padding: "8px 14px", background: "#0b1222" }}>
              <p
                style={{
                  fontFamily: "monospace",
                  fontSize: 10,
                  textTransform: "uppercase",
                  letterSpacing: 1,
                  color: "#38bdf8",
                  fontWeight: 700,
                }}
              >
                ✨ AI Graph Analyst
              </p>
              <p style={{ marginTop: 2, fontSize: 11, color: "#64748b" }}>
                Ask questions grounded in graph topology
              </p>
            </div>

            {/* Answer Display */}
            {aiAnswer ? (
              <div style={{ flex: 1, overflowY: "auto", padding: "10px 14px" }}>
                <p
                  style={{
                    fontFamily: "monospace",
                    fontSize: 10,
                    textTransform: "uppercase",
                    color: "#38bdf8",
                    marginBottom: 6,
                  }}
                >
                  Q: {aiAnswer.question}
                </p>
                <p style={{ fontSize: 12, lineHeight: 1.6, color: "#cbd5e1", whiteSpace: "pre-line" }}>
                  {aiAnswer.answer}
                </p>
                {aiAnswer.relevant_nodes?.length > 0 && (
                  <p style={{ marginTop: 8, fontFamily: "monospace", fontSize: 10, color: "#22c55e" }}>
                    ✓ {aiAnswer.relevant_nodes.length} nodes highlighted in graph
                  </p>
                )}
                <button
                  onClick={() => {
                    setAiAnswer(null);
                    setAiQuery("");
                    setHighlightedIds(new Set());
                  }}
                  style={{
                    marginTop: 8,
                    fontFamily: "monospace",
                    fontSize: 10,
                    color: "#94a3b8",
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    textDecoration: "underline",
                  }}
                >
                  ← Ask another question
                </button>
              </div>
            ) : (
              /* Starter Prompts */
              <div style={{ flex: 1, overflowY: "auto", padding: "8px 12px" }}>
                <p style={{ fontSize: 10, fontFamily: "monospace", color: "#64748b", marginBottom: 6 }}>
                  SUGGESTED QUERIES:
                </p>
                <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
                  {[
                    "What datasets are commonly used in this research?",
                    "Which models appear across these papers?",
                    "What recurring research gaps connect these papers?",
                    "How are the methodologies related across papers?",
                  ].map((q) => (
                    <button
                      key={q}
                      onClick={() => setAiQuery(q)}
                      style={{
                        borderRadius: 4,
                        border: "1px solid #1e293b",
                        background: "#0f172a",
                        padding: "6px 8px",
                        textAlign: "left",
                        fontSize: 11,
                        color: "#94a3b8",
                        cursor: "pointer",
                      }}
                      onMouseEnter={(e) => {
                        e.target.style.borderColor = "#38bdf8";
                        e.target.style.color = "#f1f5f9";
                      }}
                      onMouseLeave={(e) => {
                        e.target.style.borderColor = "#1e293b";
                        e.target.style.color = "#94a3b8";
                      }}
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* AI Input Form */}
            <form onSubmit={handleAiQuery} style={{ borderTop: "1px solid #1e293b", padding: 10, background: "#0b1222" }}>
              <textarea
                value={aiQuery}
                onChange={(e) => setAiQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleAiQuery();
                  }
                }}
                placeholder="Ask about research models, datasets, gaps…"
                rows={2}
                style={{
                  width: "100%",
                  resize: "none",
                  borderRadius: 6,
                  border: "1px solid #334155",
                  background: "#090d16",
                  padding: "6px 8px",
                  fontSize: 11,
                  color: "#e2e8f0",
                  outline: "none",
                  boxSizing: "border-box",
                }}
              />
              <button
                type="submit"
                disabled={!aiQuery.trim() || aiLoading}
                style={{
                  marginTop: 6,
                  width: "100%",
                  background: aiQuery.trim() && !aiLoading ? "#0369a1" : "#1e293b",
                  color: "#e0f2fe",
                  border: "none",
                  borderRadius: 6,
                  padding: "7px",
                  fontSize: 11,
                  fontWeight: 600,
                  cursor: aiQuery.trim() && !aiLoading ? "pointer" : "not-allowed",
                  opacity: aiQuery.trim() && !aiLoading ? 1 : 0.5,
                }}
              >
                {aiLoading ? "Synthesizing Graph… ⏳" : "Ask AI Analyst ✨"}
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Edge Detail Inspector ────────────────────────────────────────────────────
function EdgeDetailPanel({ edge, onSelectSource, onSelectTarget, onClear }) {
  const d = edge.data || {};
  const sLabel = d.source_label || edge.source;
  const tLabel = d.target_label || edge.target;
  const predicate = d.predicate || edge.label || "connected to";

  return (
    <div style={{ padding: "12px 14px" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
        <span
          style={{
            fontFamily: "monospace",
            fontSize: 9,
            textTransform: "uppercase",
            letterSpacing: 1,
            color: "#38bdf8",
            fontWeight: 700,
          }}
        >
          Relationship Details
        </span>
        <button
          onClick={onClear}
          style={{ background: "none", border: "none", color: "#64748b", cursor: "pointer", fontSize: 13 }}
        >
          ×
        </button>
      </div>

      <div
        style={{
          borderRadius: 6,
          background: "#0f172a",
          border: "1px solid #1e293b",
          padding: "10px",
          marginBottom: 10,
        }}
      >
        <span
          style={{
            display: "inline-block",
            borderRadius: 4,
            padding: "2px 6px",
            fontFamily: "monospace",
            fontSize: 10,
            textTransform: "uppercase",
            background: "#1e293b",
            color: "#38bdf8",
            marginBottom: 6,
          }}
        >
          {predicate.replace("_", " ")}
        </span>
        <p style={{ fontSize: 12, color: "#cbd5e1", lineHeight: 1.4 }}>
          <strong style={{ color: "#f1f5f9" }}>{sLabel}</strong>
          {" → "}
          <span style={{ color: "#38bdf8" }}>{predicate.replace("_", " ")}</span>
          {" → "}
          <strong style={{ color: "#f1f5f9" }}>{tLabel}</strong>
        </p>
      </div>

      {d.shared_entities && d.shared_entities.length > 0 && (
        <div style={{ marginBottom: 10 }}>
          <p style={{ fontFamily: "monospace", fontSize: 9, textTransform: "uppercase", color: "#64748b" }}>
            Shared Entities ({d.shared_entities.length})
          </p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 4 }}>
            {d.shared_entities.map((se) => (
              <span
                key={se}
                style={{
                  borderRadius: 4,
                  padding: "1px 6px",
                  fontSize: 10,
                  background: "#1e293b",
                  color: "#94a3b8",
                }}
              >
                {se}
              </span>
            ))}
          </div>
        </div>
      )}

      <div style={{ display: "flex", gap: 6, marginTop: 12 }}>
        <button
          onClick={onSelectSource}
          style={{
            flex: 1,
            borderRadius: 4,
            border: "1px solid #334155",
            background: "#1e293b",
            color: "#cbd5e1",
            padding: "5px 8px",
            fontSize: 10,
            fontFamily: "monospace",
            cursor: "pointer",
          }}
        >
          Inspect Source
        </button>
        <button
          onClick={onSelectTarget}
          style={{
            flex: 1,
            borderRadius: 4,
            border: "1px solid #334155",
            background: "#1e293b",
            color: "#cbd5e1",
            padding: "5px 8px",
            fontSize: 10,
            fontFamily: "monospace",
            cursor: "pointer",
          }}
        >
          Inspect Target
        </button>
      </div>
    </div>
  );
}

// ─── Node Detail Inspector ────────────────────────────────────────────────────
function NodeDetailPanel({ node, connectedPapers, onNavigate, onSelectRelated }) {
  const [expandAbstract, setExpandAbstract] = useState(false);
  const style = NODE_STYLES[node.data.node_type] || NODE_STYLES.concept;
  const d = node.data;

  return (
    <div style={{ padding: "12px 14px" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "flex-start", gap: 8, marginBottom: 10 }}>
        <span style={{ fontSize: 20 }}>{style.icon}</span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <p style={{ fontSize: 13, fontWeight: 700, color: "#f8fafc", lineHeight: 1.3, wordBreak: "break-word" }}>
            {d.label}
          </p>
          <span
            style={{
              display: "inline-block",
              marginTop: 4,
              borderRadius: 4,
              padding: "1px 6px",
              fontFamily: "monospace",
              fontSize: 9,
              textTransform: "uppercase",
              background: style.bg,
              color: style.text,
              border: `1px solid ${style.border}`,
            }}
          >
            {style.label || d.node_type}
          </span>
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {/* Paper Node Specifics */}
        {d.node_type === "paper" && (
          <>
            {d.authors?.length > 0 && (
              <InfoRow label="Authors" value={d.authors.slice(0, 4).join(", ")} />
            )}
            {d.publication_year && <InfoRow label="Year" value={d.publication_year} />}
            {d.venue && <InfoRow label="Venue" value={d.venue} />}
            {d.doi && <InfoRow label="DOI" value={d.doi} />}

            {d.abstract && (
              <div>
                <p style={{ fontFamily: "monospace", fontSize: 9, textTransform: "uppercase", color: "#64748b" }}>
                  Abstract
                </p>
                <p style={{ marginTop: 2, fontSize: 11, color: "#94a3b8", lineHeight: 1.5 }}>
                  {expandAbstract || d.abstract.length <= 220
                    ? d.abstract
                    : d.abstract.slice(0, 220) + "…"}
                </p>
                {d.abstract.length > 220 && (
                  <button
                    onClick={() => setExpandAbstract(!expandAbstract)}
                    style={{
                      background: "none",
                      border: "none",
                      color: "#38bdf8",
                      fontSize: 10,
                      cursor: "pointer",
                      padding: 0,
                      marginTop: 2,
                    }}
                  >
                    {expandAbstract ? "Show less" : "Read more"}
                  </button>
                )}
              </div>
            )}

            {/* Extracted Scientific Entities in this Paper */}
            {d.methods?.length > 0 && (
              <div>
                <p style={{ fontFamily: "monospace", fontSize: 9, textTransform: "uppercase", color: "#64748b" }}>
                  Methodology
                </p>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 3, marginTop: 3 }}>
                  {d.methods.map((m) => (
                    <button
                      key={m}
                      onClick={() => onSelectRelated?.(m)}
                      style={{
                        borderRadius: 3,
                        border: "1px solid #134e4a",
                        background: "#042f2e",
                        color: "#5eead4",
                        fontSize: 9,
                        padding: "1px 5px",
                        cursor: "pointer",
                      }}
                    >
                      {m}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {d.models?.length > 0 && (
              <div>
                <p style={{ fontFamily: "monospace", fontSize: 9, textTransform: "uppercase", color: "#64748b" }}>
                  Models
                </p>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 3, marginTop: 3 }}>
                  {d.models.map((m) => (
                    <button
                      key={m}
                      onClick={() => onSelectRelated?.(m)}
                      style={{
                        borderRadius: 3,
                        border: "1px solid #881337",
                        background: "#4c0519",
                        color: "#fda4af",
                        fontSize: 9,
                        padding: "1px 5px",
                        cursor: "pointer",
                      }}
                    >
                      {m}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {d.datasets?.length > 0 && (
              <div>
                <p style={{ fontFamily: "monospace", fontSize: 9, textTransform: "uppercase", color: "#64748b" }}>
                  Datasets
                </p>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 3, marginTop: 3 }}>
                  {d.datasets.map((ds) => (
                    <button
                      key={ds}
                      onClick={() => onSelectRelated?.(ds)}
                      style={{
                        borderRadius: 3,
                        border: "1px solid #78350f",
                        background: "#451a03",
                        color: "#fde68a",
                        fontSize: 9,
                        padding: "1px 5px",
                        cursor: "pointer",
                      }}
                    >
                      {ds}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Navigation buttons */}
            <div style={{ display: "flex", gap: 6, marginTop: 6 }}>
              <button
                onClick={() => onNavigate?.("papers")}
                style={{
                  flex: 1,
                  borderRadius: 4,
                  border: "1px solid #166534",
                  background: "#14532d",
                  color: "#dcfce7",
                  padding: "6px",
                  fontSize: 10,
                  fontFamily: "monospace",
                  cursor: "pointer",
                }}
              >
                📄 View Papers Tab
              </button>
              <button
                onClick={() => onNavigate?.("intelligence")}
                style={{
                  flex: 1,
                  borderRadius: 4,
                  border: "1px solid #1e3a8a",
                  background: "#172554",
                  color: "#dbeafe",
                  padding: "6px",
                  fontSize: 10,
                  fontFamily: "monospace",
                  cursor: "pointer",
                }}
              >
                🧠 Intelligence
              </button>
            </div>
          </>
        )}

        {/* Dataset Node Specifics */}
        {d.node_type === "dataset" && (
          <>
            <InfoRow label="Usage" value={`Utilized in ${d.paper_count || 1} paper(s)`} />
            {d.associated_models?.length > 0 && (
              <InfoRow label="Models" value={d.associated_models.join(", ")} />
            )}
            {d.associated_methods?.length > 0 && (
              <InfoRow label="Methods" value={d.associated_methods.join(", ")} />
            )}
          </>
        )}

        {/* Model or Algorithm Node Specifics */}
        {["model", "algorithm"].includes(d.node_type) && (
          <>
            <InfoRow label="Usage" value={`Appears in ${d.paper_count || 1} paper(s)`} />
            {d.associated_datasets?.length > 0 && (
              <InfoRow label="Datasets" value={d.associated_datasets.join(", ")} />
            )}
            {d.associated_topics?.length > 0 && (
              <InfoRow label="Topics" value={d.associated_topics.join(", ")} />
            )}
          </>
        )}

        {/* Research Gap Node Specifics */}
        {d.node_type === "gap" && (
          <>
            {d.category && <InfoRow label="Category" value={d.category} />}
            {d.source_paper_title && <InfoRow label="Identified By" value={d.source_paper_title} />}
            {d.associated_topic && <InfoRow label="Area" value={d.associated_topic} />}
            {d.description && (
              <div>
                <p style={{ fontFamily: "monospace", fontSize: 9, textTransform: "uppercase", color: "#64748b" }}>
                  Limitation Details
                </p>
                <p style={{ marginTop: 2, fontSize: 11, color: "#cbd5e1", lineHeight: 1.5 }}>
                  {d.description}
                </p>
              </div>
            )}
            {d.potential_directions && (
              <div>
                <p style={{ fontFamily: "monospace", fontSize: 9, textTransform: "uppercase", color: "#38bdf8" }}>
                  Future Direction
                </p>
                <p style={{ marginTop: 2, fontSize: 11, color: "#94a3b8", lineHeight: 1.4 }}>
                  {d.potential_directions}
                </p>
              </div>
            )}
          </>
        )}

        {/* Finding / Claim Node Specifics */}
        {d.node_type === "finding" && (
          <>
            {d.claim_type && <InfoRow label="Type" value={d.claim_type} />}
            {d.source_paper_title && <InfoRow label="Source" value={d.source_paper_title} />}
            {d.claim_text && (
              <div>
                <p style={{ fontFamily: "monospace", fontSize: 9, textTransform: "uppercase", color: "#64748b" }}>
                  Claim / Finding
                </p>
                <p style={{ marginTop: 2, fontSize: 11, color: "#cbd5e1", lineHeight: 1.5 }}>
                  {d.claim_text}
                </p>
              </div>
            )}
          </>
        )}

        {/* Research Question Specifics */}
        {d.node_type === "question" && (
          <>
            {d.question && (
              <div>
                <p style={{ fontFamily: "monospace", fontSize: 9, textTransform: "uppercase", color: "#64748b" }}>
                  Research Question
                </p>
                <p style={{ marginTop: 2, fontSize: 11, color: "#cbd5e1", lineHeight: 1.4 }}>
                  {d.question}
                </p>
              </div>
            )}
            {d.rationale && <InfoRow label="Rationale" value={d.rationale} />}
            {d.gap_addressed && <InfoRow label="Gap Addressed" value={d.gap_addressed} />}
          </>
        )}

        {/* Author Node Specifics */}
        {d.node_type === "author" && (
          <InfoRow label="Project Papers" value={`${d.paper_count || 1} paper(s) in project`} />
        )}

        {/* Topic Node Specifics */}
        {d.node_type === "topic" && (
          <>
            {d.keywords?.length > 0 && <InfoRow label="Keywords" value={d.keywords.slice(0, 6).join(", ")} />}
            {d.document_count != null && <InfoRow label="Papers" value={d.document_count} />}
          </>
        )}

        {/* Connected Papers List for non-paper entities */}
        {d.node_type !== "paper" && connectedPapers.length > 0 && (
          <div>
            <p style={{ fontFamily: "monospace", fontSize: 9, textTransform: "uppercase", color: "#64748b" }}>
              Connected Papers ({connectedPapers.length})
            </p>
            <ul style={{ marginTop: 3, display: "flex", flexDirection: "column", gap: 3, listStyle: "none", padding: 0 }}>
              {connectedPapers.slice(0, 5).map((p) => (
                <li
                  key={p.id}
                  style={{
                    fontSize: 11,
                    color: "#38bdf8",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                  title={p.data?.title || p.data?.filename}
                >
                  📄 {p.data?.title || p.data?.filename}
                </li>
              ))}
              {connectedPapers.length > 5 && (
                <li style={{ fontSize: 10, color: "#64748b" }}>
                  +{connectedPapers.length - 5} more papers
                </li>
              )}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

function InfoRow({ label, value }) {
  return (
    <div style={{ display: "flex", alignItems: "flex-start", gap: 6 }}>
      <span
        style={{
          fontFamily: "monospace",
          fontSize: 9,
          textTransform: "uppercase",
          color: "#64748b",
          flexShrink: 0,
          width: 72,
        }}
      >
        {label}
      </span>
      <span style={{ fontSize: 11, color: "#cbd5e1", wordBreak: "break-word" }}>{String(value)}</span>
    </div>
  );
}

// ─── Export wrapped in ReactFlowProvider ──────────────────────────────────────
export default function VisualKnowledgeGraph(props) {
  return (
    <ReactFlowProvider>
      <GraphCanvas {...props} />
    </ReactFlowProvider>
  );
}
