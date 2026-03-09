/**
 * 格式化时间戳为本地时间字符串
 * @param timestamp - 时间戳（毫秒）
 * @returns 格式化的时间字符串
 */
export const formatTime = (timestamp: number): string => {
  const date = new Date(timestamp);
  return date.toLocaleTimeString();
};