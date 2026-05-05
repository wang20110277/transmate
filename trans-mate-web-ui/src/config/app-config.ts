// 全局应用配置
export interface AppConfig {
  azureRegion: string;
  azureSubscriptionKey: string;
  availableVoices: string[];
}

// 从环境变量获取配置
const getConfigFromEnv = (): AppConfig => {
  return {
    azureRegion: (import.meta as any).env?.VITE_AZURE_REGION || 'eastus',
    azureSubscriptionKey: (import.meta as any).env?.VITE_AZURE_SUBSCRIPTION_KEY || '',
    availableVoices: [
      'zh-CN-XiaoxiaoNeural',
      'zh-TW-HsiaoChenNeural',
      'zh-HK-HiuMaanNeural'
    ]
  };
};

// 合并默认配置和环境变量配置
const appConfig: AppConfig = getConfigFromEnv();

export { appConfig };