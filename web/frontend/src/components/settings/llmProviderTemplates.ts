/** LLM 服务商预设模板。用于新建渠道时快速填充协议、Base URL 和推荐模型。 */

export interface ProviderTemplate {
  label: string;            // 显示名称
  channelId: string;        // 渠道标识（小写，如 minimax）
  protocol: string;         // 协议类型
  baseUrl: string;          // 基础地址
  placeholderModels: string; // 推荐模型（逗号分隔）
  protocolLabel: string;    // 协议显示标签
}

export const PROVIDER_TEMPLATES: ProviderTemplate[] = [
  {
    label: 'MiniMax',
    channelId: 'minimax',
    protocol: 'openai',
    baseUrl: 'https://api.minimax.chat/v1',
    placeholderModels: 'abab6.5s-chat',
    protocolLabel: 'OpenAI 兼容',
  },
  {
    label: 'DeepSeek 官方',
    channelId: 'deepseek',
    protocol: 'openai',
    baseUrl: 'https://api.deepseek.com/v1',
    placeholderModels: 'deepseek-chat,deepseek-reasoner',
    protocolLabel: 'OpenAI 兼容',
  },
  {
    label: '通义千问 (DashScope)',
    channelId: 'dashscope',
    protocol: 'openai',
    baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    placeholderModels: 'qwen-plus,qwen-max',
    protocolLabel: 'OpenAI 兼容',
  },
  {
    label: '智谱 GLM',
    channelId: 'zhipu',
    protocol: 'openai',
    baseUrl: 'https://open.bigmodel.cn/api/paas/v4',
    placeholderModels: 'glm-4-plus',
    protocolLabel: 'OpenAI 兼容',
  },
  {
    label: 'Moonshot (月之暗面)',
    channelId: 'moonshot',
    protocol: 'openai',
    baseUrl: 'https://api.moonshot.cn/v1',
    placeholderModels: 'moonshot-v1-8k',
    protocolLabel: 'OpenAI 兼容',
  },
  {
    label: '火山方舟 (豆包)',
    channelId: 'volcengine',
    protocol: 'openai',
    baseUrl: 'https://ark.cn-beijing.volces.com/api/v3',
    placeholderModels: 'doubao-pro-32k',
    protocolLabel: 'OpenAI 兼容',
  },
  {
    label: 'SiliconFlow',
    channelId: 'siliconflow',
    protocol: 'openai',
    baseUrl: 'https://api.siliconflow.cn/v1',
    placeholderModels: 'Qwen/Qwen2.5-7B-Instruct',
    protocolLabel: 'OpenAI 兼容',
  },
  {
    label: 'AIHubmix',
    channelId: 'aihubmix',
    protocol: 'openai',
    baseUrl: 'https://aihubmix.com/v1',
    placeholderModels: 'gpt-4o-mini',
    protocolLabel: 'OpenAI 兼容',
  },
  {
    label: 'OpenAI 官方',
    channelId: 'openai',
    protocol: 'openai',
    baseUrl: 'https://api.openai.com/v1',
    placeholderModels: 'gpt-4o,gpt-4o-mini',
    protocolLabel: 'OpenAI 兼容',
  },
  {
    label: 'Gemini 官方',
    channelId: 'gemini',
    protocol: 'gemini',
    baseUrl: '',
    placeholderModels: 'gemini-2.5-flash',
    protocolLabel: 'Gemini',
  },
  {
    label: 'Ollama 本地',
    channelId: 'ollama',
    protocol: 'ollama',
    baseUrl: 'http://127.0.0.1:11434/v1',
    placeholderModels: 'qwen2.5:7b',
    protocolLabel: 'Ollama',
  },
  {
    label: '自定义渠道',
    channelId: 'custom',
    protocol: 'openai',
    baseUrl: '',
    placeholderModels: '',
    protocolLabel: 'OpenAI 兼容',
  },
];

export const PROTOCOL_OPTIONS = [
  { value: 'openai', label: 'OpenAI 兼容' },
  { value: 'gemini', label: 'Gemini' },
  { value: 'ollama', label: 'Ollama' },
];
