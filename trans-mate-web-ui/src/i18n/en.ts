// English dictionary (structure mirrors zh.ts)
export const en = {
  home: {
    newChat: 'New chat',
    recent: 'Recent',
    expandSidebar: 'Expand sidebar',
    collapseSidebar: 'Collapse sidebar',
    connected: 'Connected',
    connecting: 'Connecting…',
    ttsEnable: 'Enable voice',
    ttsDisable: 'Disable voice',
    ttsLabel: 'Voice',
    ttsSpeaking: 'Speaking',
    ttsMuted: 'Muted',
    greeting: 'What can I help you with?',
    recommend: 'Recommended for you',
    inputPlaceholder: 'Type a message, or tap the mic to speak…',
    suggestions: [
      'Translate "会议将于明天下午三点开始" into English',
      "Check today's weather in Beijing",
      'Search major AI news from the past week',
      'Look up the latest Kweichow Moutai stock quote'
    ],
    prefTitle: 'Preferences',
    prefButton: 'Preferences',
    settings: 'Settings',
    openSettings: 'Open settings',
    langLabel: 'Language',
    themeLabel: 'Theme',
    themeLight: 'Light',
    themeDark: 'Dark',
    connLabel: 'Connection',
    apply: 'Apply',
    connHint: 'The page reloads after changing the server address'
  },
  errors: {
    noSpeech: 'No speech recognized, please try again',
    transcribeFailed: 'Transcription failed: {msg}',
    micDenied: 'Cannot access microphone: {msg}',
    unknown: 'Unknown error',
    invalidUrl: 'Server address must start with http:// or https://',
    wsNotConnected: 'WebSocket not connected — connect to the server first'
  },
  settings: {
    backHome: 'Back to home',
    groupBasic: 'Basics',
    groupCapability: 'Capabilities',
    notOpen: 'Coming soon',
    items: {
      general: { label: 'General', desc: 'General preferences and behavior, such as defaults and data management.' },
      appearance: { label: 'Appearance', desc: 'Theme and display options, such as color theme and font size.' },
      memory: { label: 'Memory', desc: 'Conversation memory and long-term preferences, so the assistant remembers what matters.' },
      skills: { label: 'Skills', desc: "View and manage the assistant's available skills and plugins." },
      rag: { label: 'RAG', desc: 'Retrieval-augmented generation — upload documents for more accurate answers.' },
      mcp: { label: 'MCP', desc: 'Model Context Protocol services and configuration.' }
    }
  },
  chat: {
    emptyConversations: 'No conversations yet — click "New chat" to start',
    untitled: 'New conversation',
    deleteConversation: 'Delete conversation',
    listening: 'Listening — tap the mic to stop',
    transcribing: 'Transcribing…',
    micTranscribing: 'Transcribing speech…',
    micStop: 'Stop recording and transcribe',
    micTitle: 'Voice input',
    send: 'Send',
    stopGenerate: 'Stop generating',
    speak: 'Read aloud',
    stopSpeak: 'Stop reading',
    speakMuted: 'Globally muted',
    expand: 'Expand',
    collapse: 'Collapse',
    thinking: 'Thinking...',
    runningTools: 'Running tools...',
    agentWorking: 'Agent {agent} is working...',
    toolRunning: 'Running',
    toolDone: 'Done',
    toolArgs: 'Arguments',
    toolResult: 'Result',
    toolWaiting: 'Waiting for tool execution...'
  }
}
