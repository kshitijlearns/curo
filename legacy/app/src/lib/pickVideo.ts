/**
 * Pick a recorded reel from the phone's library (MP4 or MOV, up to 90 seconds). The system
 * picker asks for no library permission on recent iOS and Android.
 */
import * as ImagePicker from 'expo-image-picker';

import { MAX_SECONDS, type PickedVideo } from '@/api/simulator';

export async function pickVideo(): Promise<PickedVideo | null> {
  const res = await ImagePicker.launchImageLibraryAsync({
    mediaTypes: ['videos'],
    allowsEditing: false,
    videoMaxDuration: MAX_SECONDS,
    quality: 1,
  });
  if (res.canceled || !res.assets?.length) return null;
  const a = res.assets[0];
  return {
    uri: a.uri,
    name: a.fileName ?? 'my_reel.mp4',
    mimeType: a.mimeType ?? null,
    durationS: a.duration != null ? a.duration / 1000 : null, // the picker gives milliseconds
    width: a.width || null,
    height: a.height || null,
  };
}
