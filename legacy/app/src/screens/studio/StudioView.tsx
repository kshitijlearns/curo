import { useState } from 'react';
import { ScrollView, View } from 'react-native';

import { CaptionStage, FinalStage } from './CaptionFinal';
import { useStudio } from './derived';
import { IdeasStage } from './IdeasStage';
import { IdeaStage, ScriptStage } from './ScriptStage';
import { StepsBar } from './StepsBar';
import { StoryboardStage } from './StoryboardStage';
import { ValidateChat } from './ValidateChat';
import { AskCuroThread } from '@/components/AskCuroThread';
import { useSheetScroll } from '@/screens/shell/useSheetScroll';
import { chatTarget, useApp } from '@/state/app';

/** Studio: the validate chat when opened from the nav, otherwise the five steps. */
export function StudioView() {
  const ref = useSheetScroll();
  const { st, validating } = useStudio();
  const [height, setHeight] = useState(520);
  // Ask Curo's answers to questions asked on this step (changes show in the step itself).
  const threadKey = useApp((s) => chatTarget({ ...s, tab: 'studio' })?.key ?? null);
  const asked = useApp((s) => (threadKey ? (s.chat[threadKey]?.length ?? 0) : 0));

  return (
    <ScrollView
      ref={ref}
      onLayout={(e) => setHeight(e.nativeEvent.layout.height)}
      contentContainerStyle={{ flexGrow: 1 }}
      keyboardShouldPersistTaps="handled"
      showsVerticalScrollIndicator={false}
    >
      {validating ? (
        <View style={{ flexGrow: 1 }}>
          <ValidateChat minHeight={asked ? 0 : Math.max(height, 420)} quiet={asked > 0} />
          <View style={{ paddingHorizontal: 20, paddingBottom: 26 }}>
            <AskCuroThread threadKey={threadKey} />
          </View>
        </View>
      ) : (
        <View style={{ paddingTop: 22, paddingHorizontal: 20, paddingBottom: 26 }}>
          <StepsBar />
          <View style={{ paddingTop: 20 }}>
            {st.stage === 'ideas' ? <IdeasStage /> : null}
            {st.stage === 'idea' ? <IdeaStage /> : null}
            {st.stage === 'script' ? <ScriptStage /> : null}
            {st.stage === 'storyboard' ? <StoryboardStage /> : null}
            {st.stage === 'caption' ? <CaptionStage /> : null}
            {st.stage === 'final' ? <FinalStage /> : null}
          </View>
          {st.stage !== 'final' ? <AskCuroThread threadKey={threadKey} /> : null}
        </View>
      )}
    </ScrollView>
  );
}
