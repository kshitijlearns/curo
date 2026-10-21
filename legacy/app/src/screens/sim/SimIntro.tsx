import { StyleSheet, View } from 'react-native';
import Svg, { Circle } from 'react-native-svg';

import { useSamples } from '@/api/hooks';
import { Icon } from '@/components/Icon';
import { Appear, Press, Spin } from '@/components/motion';
import { ReelThumb } from '@/components/ReelThumb';
import { Eyebrow, Txt } from '@/components/Txt';
import { ChoiceChips, OutlinePill, Pill, PrimaryButton, Switch } from '@/components/ui';
import { formatDuration } from '@/lib/format';
import { pickVideo } from '@/lib/pickVideo';
import { AUDIENCES } from '@/lib/simText';
import { useApp, type SimUpload } from '@/state/app';
import { colors } from '@/theme';

/** Spinner ring used while uploading and simulating. */
export function LoadingRing({ size, track }: { size: number; track: string }) {
  return (
    <Spin>
      <Svg width={size} height={size} viewBox="0 0 84 84">
        <Circle cx={42} cy={42} r={36} fill="none" stroke={track} strokeWidth={size > 60 ? 6 : 8} />
        <Circle
          cx={42}
          cy={42}
          r={36}
          fill="none"
          stroke={colors.blue}
          strokeWidth={size > 60 ? 6 : 8}
          strokeLinecap="round"
          strokeDasharray="70 157"
        />
      </Svg>
    </Spin>
  );
}

/** "0:41 · 1080 × 1920 · ready". A length the phone couldn't read is left out (the API reads
 * it from the file before simulating), never shown as 0:00. */
export function uploadLine(u: SimUpload): string {
  const parts = [
    u.durationS > 0 ? formatDuration(u.durationS) : null,
    u.width && u.height ? `${u.width} × ${u.height}` : null,
    'ready',
  ];
  return parts.filter(Boolean).join(' · ');
}

/** The demo's sample recordings (a real video provider offers none, and this shows nothing). */
export function SampleTakes({
  onPick,
  label,
}: {
  onPick: (name: string, title: string) => void;
  label: string;
}) {
  const samples = useSamples().data ?? [];
  if (!samples.length) return null;
  return (
    <View style={{ gap: 8 }}>
      <Txt size={13} color={colors.muted} style={{ marginHorizontal: 2 }}>
        {label}
      </Txt>
      {samples.map((s) => (
        <Press
          key={s.name}
          onPress={() => onPick(s.name, s.title)}
          accessibilityLabel={`Use the sample: ${s.title}`}
          style={styles.sample}
        >
          <Icon name="simulate" size={16} color={colors.blue} />
          <View style={{ flex: 1, gap: 2 }}>
            <Txt size={14} weight={600}>
              {s.title}
            </Txt>
            <Txt size={12.5} color={colors.muted}>
              {s.description}
            </Txt>
          </View>
        </Press>
      ))}
    </View>
  );
}

/** Upload the recorded reel, pick the audience, run (logic doc §13 inputs). */
export function SimIntro() {
  const sim = useApp((s) => s.sim);
  const studioIdea = useApp((s) => s.studio.ideaTitle);
  const uploadPicked = useApp((s) => s.uploadPicked);
  const uploadSample = useApp((s) => s.uploadSample);
  const replaceUpload = useApp((s) => s.replaceUpload);
  const toggleLink = useApp((s) => s.toggleLink);
  const setAudience = useApp((s) => s.setAudience);
  const runSim = useApp((s) => s.runSim);
  const upload = sim.upload;

  const pick = async () => {
    const video = await pickVideo();
    if (video) await uploadPicked(video);
  };

  return (
    <Appear style={styles.wrap}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        <Txt size={20} weight={600}>
          Simulate your recorded reel
        </Txt>
        <Pill label="Beta" bg={colors.lavender} height={22} fontSize={11.5} />
      </View>
      <Txt size={14.5} lh={1.55} color={colors.muted} style={{ marginTop: -4, marginBottom: 4 }}>
        Upload the video once you’ve recorded it. Curo estimates how it’s likely to land before you
        post.
      </Txt>

      {!upload && !sim.uploading ? (
        <>
          <Press onPress={pick} accessibilityLabel="Upload your recorded reel" style={styles.drop}>
            <View style={styles.dropIcon}>
              <Icon name="upload" size={22} color={colors.white} strokeWidth={2} />
            </View>
            <Txt size={16} weight={600}>
              Upload your recorded reel
            </Txt>
            <Txt size={12.5} color={colors.muted}>
              MP4 or MOV · up to 90 seconds
            </Txt>
          </Press>
          <SampleTakes onPick={uploadSample} label="No recording yet? Try a sample take:" />
        </>
      ) : null}
      {sim.uploading ? (
        <Appear kind="fade" style={styles.uploading}>
          <LoadingRing size={40} track={colors.white} />
          <Txt size={14} weight={600}>
            Uploading…
          </Txt>
        </Appear>
      ) : null}
      {upload && !sim.uploading ? (
        <Appear kind="rise" style={styles.file}>
          <View style={{ width: 56, height: 76, borderRadius: 14, overflow: 'hidden' }}>
            <ReelThumb tone={2} compact height={76} />
          </View>
          <View style={{ flex: 1, gap: 4 }}>
            <Txt size={15} weight={600} numberOfLines={1}>
              {upload.name}
            </Txt>
            <Txt size={12.5} color={colors.muted}>
              {uploadLine(upload)}
            </Txt>
          </View>
          <OutlinePill label="Replace" height={34} onPress={replaceUpload} />
        </Appear>
      ) : null}

      {studioIdea ? (
        <Press
          onPress={toggleLink}
          accessibilityRole="switch"
          accessibilityState={{ checked: sim.linked }}
          accessibilityLabel="Compare with Studio draft"
          style={styles.link}
        >
          <View style={{ flex: 1, gap: 3 }}>
            <Eyebrow color={colors.muted}>Compare with Studio draft</Eyebrow>
            <Txt size={14.5} weight={600} lh={1.35}>
              {studioIdea}
            </Txt>
          </View>
          <Switch on={sim.linked} />
        </Press>
      ) : null}

      <Txt size={18} weight={600} style={{ marginTop: 10 }}>
        Who is this for?
      </Txt>
      <ChoiceChips options={AUDIENCES} value={sim.audience} onChange={setAudience} />
      <Txt size={13} lh={1.6} color={colors.muted} style={{ marginHorizontal: 2, marginTop: 2 }}>
        Curo compares your reel with your own past reels, your audience’s past behaviour and recent
        reels from the creators you track.
      </Txt>
      <PrimaryButton
        label="Run simulation"
        icon="simulate"
        height={58}
        disabled={!upload || sim.uploading}
        onPress={() => void runSim()}
        style={{ marginTop: 6 }}
      />
    </Appear>
  );
}

const styles = StyleSheet.create({
  wrap: { paddingTop: 24, paddingHorizontal: 20, paddingBottom: 26, gap: 12 },
  drop: {
    height: 150,
    borderRadius: 24,
    borderWidth: 1.5,
    borderStyle: 'dashed',
    borderColor: colors.blue,
    backgroundColor: colors.white,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
  },
  dropIcon: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: colors.blue,
    alignItems: 'center',
    justifyContent: 'center',
  },
  uploading: {
    height: 150,
    borderRadius: 24,
    backgroundColor: colors.gray,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
  },
  file: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
    borderWidth: 1.5,
    borderColor: colors.blue,
    borderRadius: 24,
    padding: 12,
    backgroundColor: colors.white,
  },
  link: {
    borderWidth: 1,
    borderColor: colors.gray,
    backgroundColor: colors.white,
    borderRadius: 22,
    paddingVertical: 14,
    paddingHorizontal: 16,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
  },
  sample: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    borderRadius: 18,
    backgroundColor: colors.gray,
    paddingVertical: 12,
    paddingHorizontal: 14,
  },
});
