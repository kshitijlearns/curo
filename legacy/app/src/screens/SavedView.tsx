import { ScrollView, StyleSheet, View } from 'react-native';

import { Icon } from '@/components/Icon';
import { Appear, Press } from '@/components/motion';
import { Sketch, type SketchKind } from '@/components/Sketch';
import { Txt } from '@/components/Txt';
import { useMe, useSaved, useSaveOpportunity } from '@/api/hooks';
import { Pill } from '@/components/ui';
import { TAG_STYLE } from '@/mock/data';
import { useSheetScroll } from '@/screens/shell/useSheetScroll';
import { useApp, type StudioStage } from '@/state/app';
import { colors } from '@/theme';

const STAGE_LABEL: Record<StudioStage, string> = {
  ideas: 'Idea',
  idea: 'Script',
  script: 'Script',
  storyboard: 'Visuals',
  caption: 'Caption',
  final: 'Final draft',
};

/** Saved: bookmarked opportunity areas and Studio drafts (logic doc §14). Opportunities keep
 * the score from when they were saved beside today's, and say when a dated window passed. */
export function SavedView() {
  const ref = useSheetScroll();
  const openSavedOpp = useApp((s) => s.openSavedOpp);
  const openDraft = useApp((s) => s.openDraft);
  const showToast = useApp((s) => s.showToast);
  const saveOpp = useSaveOpportunity();
  const saved = useSaved().data;
  const now = useMe().data?.now;
  const opps = saved?.opportunities ?? [];
  const drafts = saved?.drafts ?? [];

  return (
    <ScrollView
      ref={ref}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
    >
      <Appear style={{ gap: 12 }}>
        <SectionHead title="Opportunity areas" count={opps.length} />
        {opps.length === 0 ? (
          <Empty text="Nothing saved yet. Tap the bookmark on any opportunity area to keep it here." />
        ) : null}
        {opps.map((o) => (
          <Appear kind="rise" key={o.id} style={styles.oppRow}>
            <Press
              onPress={() => openSavedOpp(o.id)}
              accessibilityLabel={`Open ${o.name}`}
              style={{ flex: 1, gap: 6 }}
            >
              <View
                style={{ flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}
              >
                <Pill
                  label={o.tag}
                  bg={TAG_STYLE[o.tag].bg}
                  fg={TAG_STYLE[o.tag].fg}
                  height={24}
                  fontSize={12}
                />
                <Txt size={12.5} color={colors.muted}>
                  {scoreLine(o.score_when_saved, o.score_today)}
                </Txt>
                {o.window_passed ? (
                  <Pill label="Window passed" bg={colors.gray} height={22} fontSize={11.5} />
                ) : null}
              </View>
              <Txt size={16} weight={600}>
                {o.name}
              </Txt>
            </Press>
            <Press
              onPress={() =>
                saveOpp.mutate(
                  { id: o.id, save: false },
                  { onSuccess: () => showToast('Removed from saved.') },
                )
              }
              accessibilityLabel={`Remove ${o.name} from saved`}
              style={styles.unsave}
            >
              <Icon name="bookmark" size={18} color={colors.blue} filled />
            </Press>
          </Appear>
        ))}

        <View style={{ marginTop: 14 }}>
          <SectionHead title="Studio drafts" count={drafts.length} />
        </View>
        {drafts.length === 0 ? (
          <Empty text="No drafts yet. Use “Save draft” in Studio and it will show up here." />
        ) : null}
        {drafts.map((d) => (
          <Appear kind="rise" key={d.id}>
            <Press
              onPress={() => openDraft(d.id)}
              accessibilityLabel={`Open draft ${d.title}`}
              style={styles.draftRow}
            >
              <View style={styles.draftThumb}>
                <Sketch kind={(d.icon_key ?? 'closeup') as SketchKind} />
              </View>
              <View style={{ flex: 1, gap: 4 }}>
                <Txt size={11.5} weight={600} ls={0.08} upper color={colors.muted}>
                  {d.opportunity ?? 'Your own idea'}
                </Txt>
                <Txt size={15} weight={600} lh={1.35}>
                  {d.title}
                </Txt>
                <View style={{ flexDirection: 'row', gap: 6, alignItems: 'center' }}>
                  <Pill
                    label={STAGE_LABEL[d.step]}
                    bg={colors.lavender}
                    height={22}
                    fontSize={11.5}
                  />
                  <Txt size={12} color={colors.muted}>
                    {savedWhen(d.saved_at, now)}
                  </Txt>
                </View>
              </View>
              <Icon name="chevronRight" size={18} color={colors.blue} strokeWidth={2} />
            </Press>
          </Appear>
        ))}
      </Appear>
    </ScrollView>
  );
}

/** "Today", "Yesterday" or the date — against CURO's clock (the API's "now"), not the phone's. */
function savedWhen(at: string | null | undefined, now: string | undefined): string {
  if (!at) return '';
  const when = new Date(at);
  const today = now ? new Date(now) : new Date();
  const days = Math.floor((today.getTime() - when.getTime()) / 86_400_000);
  if (days <= 0) return 'Today';
  if (days === 1) return 'Yesterday';
  return when.toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
}

function scoreLine(then: number | null | undefined, today: number): string {
  const now = Math.round(today);
  if (then == null) return `${now}/10`;
  const was = Math.round(then);
  return was === now ? `${now}/10` : `${was}/10 when saved · ${now}/10 today`;
}

function SectionHead({ title, count }: { title: string; count: number }) {
  return (
    <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline' }}>
      <Txt size={20} weight={600}>
        {title}
      </Txt>
      <Txt size={13} color={colors.muted}>
        {count} saved
      </Txt>
    </View>
  );
}

function Empty({ text }: { text: string }) {
  return (
    <View style={styles.empty}>
      <Txt size={14} lh={1.55}>
        {text}
      </Txt>
    </View>
  );
}

const styles = StyleSheet.create({
  content: { paddingTop: 24, paddingHorizontal: 20, paddingBottom: 28 },
  oppRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    borderWidth: 1,
    borderColor: colors.gray,
    borderRadius: 22,
    paddingVertical: 14,
    paddingLeft: 16,
    paddingRight: 12,
  },
  unsave: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.white,
    alignItems: 'center',
    justifyContent: 'center',
  },
  draftRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
    borderWidth: 1,
    borderColor: colors.gray,
    borderRadius: 22,
    padding: 12,
    backgroundColor: colors.white,
  },
  draftThumb: {
    width: 54,
    height: 72,
    borderWidth: 1,
    borderColor: colors.gray,
    borderRadius: 12,
    overflow: 'hidden',
  },
  empty: { padding: 18, borderRadius: 22, backgroundColor: colors.gray },
});
