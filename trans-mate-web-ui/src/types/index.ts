
// 定义类型
interface Message {
  role?: string;
  content?: string;
  timestamp?: number;
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

export type { Message, WebSocketMessage, ParsedWebSocketMessage };