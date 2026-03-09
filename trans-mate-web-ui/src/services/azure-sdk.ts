import * as SpeechSDK from 'microsoft-cognitiveservices-speech-sdk';

// 全局Azure认知服务SDK实例
let speechConfig: SpeechSDK.SpeechConfig | null = null;
let avatarSynthesizer: SpeechSDK.AvatarSynthesizer | null = null;
let peerConnection: RTCPeerConnection | null = null;
let avatarSessionInitialized = false;

// 获取或创建语音配置
export const getOrCreateSpeechConfig = (subscriptionKey: string, region: string , voiceName: string): SpeechSDK.SpeechConfig => {
  if (!speechConfig) {
    speechConfig = SpeechSDK.SpeechConfig.fromSubscription(subscriptionKey, region);
    speechConfig.speechSynthesisVoiceName = voiceName;
  }
  return speechConfig;
};

// 更新语音配置
export const updateSpeechConfig = (subscriptionKey: string, region: string, voiceName: string) => {
  // 重新创建语音配置，因为SpeechConfig的属性是只读的
  speechConfig = SpeechSDK.SpeechConfig.fromSubscription(subscriptionKey, region);
  speechConfig.speechSynthesisVoiceName = voiceName;
};

// 获取当前语音配置
export const getCurrentSpeechConfig = (): SpeechSDK.SpeechConfig | null => {
  return speechConfig;
};

// 设置Avatar合成器
export const setAvatarSynthesizer = (synthesizer: SpeechSDK.AvatarSynthesizer) => {
  avatarSynthesizer = synthesizer;
};

// 获取Avatar合成器
export const getAvatarSynthesizer = (): SpeechSDK.AvatarSynthesizer | null => {
  return avatarSynthesizer;
};

// 设置Peer连接
export const setPeerConnection = (connection: RTCPeerConnection) => {
  peerConnection = connection;
};

// 获取Peer连接
export const getPeerConnection = (): RTCPeerConnection | null => {
  return peerConnection;
};

// 重置所有实例
export const resetAzureInstances = () => {
  speechConfig = null;
  avatarSynthesizer = null;
  peerConnection = null;
  avatarSessionInitialized = false;
};

// 获取或设置Avatar会话初始化状态
export const setAvatarSessionInitialized = (initialized: boolean) => {
  avatarSessionInitialized = initialized;
};

export const isAvatarSessionInitialized = (): boolean => {
  return avatarSessionInitialized;
};

// 导出整个SDK
export { SpeechSDK };