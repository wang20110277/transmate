
// 定义类型
interface ToolCallBlock {
  id: string;
  name: string;
  args?: unknown;
  result?: string;
  running: boolean;
}

interface Message {
  role?: string;
  content?: string;
  timestamp?: number;
  // 智能体扩展：工具调用块（assistant 消息）
  toolCalls?: ToolCallBlock[];
  // 智能体扩展：正在流式输出中
  streaming?: boolean;
  // 智能体扩展：该条消息使用的智能体（base_agent 等）
  agent?: string;
}

// WebSocket 智能体事件（ZCode 式事件流）
type AgentEvent =
  | { type: 'status'; message: string }
  | { type: 'agent_start'; agent: string }
  | { type: 'token'; content: string }
  | { type: 'tool_call'; id: string; name: string; args?: unknown }
  | { type: 'tool_result'; id: string; name: string; result: string }
  | { type: 'conversation_created'; conversation_id: number }
  | { type: 'done'; content: string; tool_events?: ToolCallBlock[] }
  | { type: 'stopped'; message: string }
  | { type: 'error'; message: string };

// 会话
interface Conversation {
  id: number;
  user_id: string;
  title: string;
  created_at?: string;
  updated_at?: string;
}

// 会话消息（后端返回）
interface ConversationMessage {
  id: number;
  conversation_id: number;
  role: string;
  content: string;
  tool_events?: string | null;
  created_at?: string;
}

interface WebSocketMessage {
  type: string;
  data: string;
  timestamp: number;
}

interface ParsedWebSocketMessage {
  // 纯文本格式的消息内容
  text: string;
  timestamp?: number;
}

export type {
  Message,
  ToolCallBlock,
  AgentEvent,
  Conversation,
  ConversationMessage,
  WebSocketMessage,
  ParsedWebSocketMessage
};
