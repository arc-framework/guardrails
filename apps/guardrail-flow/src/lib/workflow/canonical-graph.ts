/**
 * Canonical guardrail pipeline as React Flow nodes + edges.
 *
 * The 12 stages match Spec 010's STAGE_DESCRIPTORS. Coordinates are
 * hand-tuned (no layout algorithm) so the graph stays operator-recognizable
 * across renders — same shape every time helps muscle memory.
 *
 * The graph topology is fixed; the per-stage execution state lives in
 * WorkflowNodeState and is derived from the lifecycle replay + live SSE
 * by `derive-node-state.ts` (built in T039).
 */

import type { Edge, Node } from "reactflow";
import type { StageName } from "@/types/api";

export interface CanonicalNodeData {
  stage: StageName;
  label: string;
  description: string;
}

export const CANONICAL_NODES: Node<CanonicalNodeData>[] = [
  {
    id: "validate",
    type: "stage",
    position: { x: 0, y: 100 },
    data: { stage: "validate", label: "Validate", description: "Input shape + size check" },
  },
  {
    id: "defend",
    type: "stage",
    position: { x: 150, y: 100 },
    data: { stage: "defend", label: "Defend", description: "Jailbreak detection" },
  },
  {
    id: "classify",
    type: "stage",
    position: { x: 300, y: 100 },
    data: { stage: "classify", label: "Classify", description: "PII / entity inspection" },
  },
  {
    id: "deception_inspect",
    type: "stage",
    position: { x: 450, y: 50 },
    data: {
      stage: "deception_inspect",
      label: "Deception",
      description: "Multi-turn drift score",
    },
  },
  {
    id: "sanitize",
    type: "stage",
    position: { x: 450, y: 150 },
    data: { stage: "sanitize", label: "Sanitize", description: "Placeholder substitution" },
  },
  {
    id: "route",
    type: "stage",
    position: { x: 600, y: 100 },
    data: { stage: "route", label: "Route", description: "Policy decision" },
  },
  {
    id: "execute",
    type: "stage",
    position: { x: 750, y: 50 },
    data: { stage: "execute", label: "Execute", description: "Strategy invocation" },
  },
  {
    id: "refusal",
    type: "stage",
    position: { x: 750, y: 200 },
    data: { stage: "refusal", label: "Refusal", description: "Block path" },
  },
  {
    id: "verify",
    type: "stage",
    position: { x: 900, y: 50 },
    data: { stage: "verify", label: "Verify", description: "Fidelity scoring" },
  },
  {
    id: "rehydrate",
    type: "stage",
    position: { x: 1050, y: 50 },
    data: { stage: "rehydrate", label: "Rehydrate", description: "Placeholder restoration" },
  },
  {
    id: "decision_emit",
    type: "stage",
    position: { x: 1200, y: 100 },
    data: { stage: "decision_emit", label: "Decision", description: "DecisionRecord emit" },
  },
  {
    id: "report",
    type: "stage",
    position: { x: 1350, y: 100 },
    data: { stage: "report", label: "Report", description: "Reporter dispatch" },
  },
];

export const CANONICAL_EDGES: Edge[] = [
  { id: "validate->defend", source: "validate", target: "defend" },
  { id: "defend->classify", source: "defend", target: "classify" },
  { id: "classify->deception_inspect", source: "classify", target: "deception_inspect" },
  { id: "classify->sanitize", source: "classify", target: "sanitize" },
  { id: "deception_inspect->route", source: "deception_inspect", target: "route" },
  { id: "sanitize->route", source: "sanitize", target: "route" },
  {
    id: "route->execute",
    source: "route",
    target: "execute",
    label: "pass / redact / clarify",
  },
  {
    id: "route->refusal",
    source: "route",
    target: "refusal",
    label: "block / refuse",
  },
  { id: "execute->verify", source: "execute", target: "verify" },
  { id: "verify->rehydrate", source: "verify", target: "rehydrate" },
  { id: "rehydrate->decision_emit", source: "rehydrate", target: "decision_emit" },
  { id: "refusal->decision_emit", source: "refusal", target: "decision_emit" },
  { id: "decision_emit->report", source: "decision_emit", target: "report" },
];

/**
 * The 12 stage names in canonical-graph order. Useful for default
 * WorkflowNodeState construction and iteration.
 */
export const CANONICAL_STAGES: readonly StageName[] = CANONICAL_NODES.map((n) => n.data.stage);
