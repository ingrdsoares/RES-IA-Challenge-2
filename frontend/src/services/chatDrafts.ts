const prefix = 'chat-draft:';

export function chatDraftKey(account: string, company: string, conversation?: string) {
  return prefix + JSON.stringify([account, company, conversation ?? null]);
}

export function clearChatDrafts() {
  for (const key of Object.keys(sessionStorage)) {
    if (key.startsWith(prefix)) sessionStorage.removeItem(key);
  }
}
