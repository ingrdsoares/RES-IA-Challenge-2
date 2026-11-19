import { useLayoutEffect, useRef } from 'react';
import type { MouseEvent, ReactNode } from 'react';
import { ArrowLeft } from 'lucide-react';
import './record-detail.css';

function followsLink(event: MouseEvent<HTMLAnchorElement>) {
  return event.button === 0 && !event.metaKey && !event.ctrlKey &&
    !event.altKey && !event.shiftKey && !event.defaultPrevented;
}

export function useRecordNavigation(companyId: string, listHref: string, id: string | null, ready: boolean) {
  const heading = useRef<HTMLHeadingElement>(null);
  const list = useRef<HTMLUListElement>(null);
  const context = companyId + listHref;

  useLayoutEffect(() => {
    if (!ready || !window.matchMedia('(max-width: 1023px)').matches) return;
    if (id !== null) {
      heading.current?.focus({ preventScroll: true });
      heading.current?.scrollIntoView({ block: 'start' });
      return;
    }
    const saved = history.state?.recordList;
    if (saved?.context !== context) return;
    const item = list.current?.querySelector<HTMLAnchorElement>(
      `[data-record-id="${CSS.escape(saved.id)}"]`,
    );
    if (!item) return;
    item.focus({ preventScroll: true });
    if (typeof saved.top === 'number') window.scrollBy(0, item.getBoundingClientRect().top - saved.top);
    else item.scrollIntoView({ block: 'nearest' });
  }, [context, id, ready]);

  function openRecord(event: MouseEvent<HTMLAnchorElement>) {
    if (id !== null || !followsLink(event)) return;
    const link = event.currentTarget;
    event.preventDefault();
    // Keep the originating row on the list's own history entry, including across reloads.
    history.replaceState({ ...history.state, recordList: {
      context, id: link.dataset.recordId, top: link.getBoundingClientRect().top,
    } }, '');
    window.location.hash = link.hash;
    history.replaceState({ ...history.state, recordOrigin: context }, '');
  }

  function returnToList(event: MouseEvent<HTMLAnchorElement>) {
    if (!followsLink(event)) return;
    event.preventDefault();
    if (history.state?.recordOrigin === context) {
      history.back();
    } else {
      window.location.hash = listHref;
      history.replaceState({ ...history.state, recordList: { context, id } }, '');
    }
  }

  return { heading, list, openRecord, returnToList };
}

export function RecordDetail({ title, listHref, backLabel, navigation, children }: {
  title: string;
  listHref: string;
  backLabel: string;
  navigation: ReturnType<typeof useRecordNavigation>;
  children?: ReactNode;
}) {
  return (
    <aside className="record-detail panel space-y-4" aria-labelledby="record-detail-title">
      <h2 id="record-detail-title" className="text-lg font-bold" ref={navigation.heading} tabIndex={-1}>
        {title}
      </h2>
      <a className="record-return" href={listHref} onClick={navigation.returnToList}>
        <ArrowLeft size={17} aria-hidden /> {backLabel}
      </a>
      {children}
    </aside>
  );
}
