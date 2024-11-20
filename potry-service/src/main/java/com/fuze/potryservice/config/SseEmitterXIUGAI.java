package com.fuze.potryservice.config;

import org.springframework.http.MediaType;
import org.springframework.lang.Nullable;
import org.springframework.util.StringUtils;
import org.springframework.web.servlet.mvc.method.annotation.ResponseBodyEmitter;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.util.LinkedHashSet;
import java.util.Set;
import java.util.UUID;

public class SseEmitterXIUGAI extends ResponseBodyEmitter {
    private static final MediaType TEXT_PLAIN = MediaType.TEXT_PLAIN;

    public SseEmitterXIUGAI() {
    }

    public SseEmitterXIUGAI(Long timeout) {
        super(timeout);
    }

    public interface SseEventBuilder {
        SseEmitterXIUGAI.SseEventBuilder id(String id);
        SseEmitterXIUGAI.SseEventBuilder data(Object object);
        SseEmitterXIUGAI.SseEventBuilder data(Object object, @Nullable MediaType mediaType);
        void send(SseEmitter emitter) throws IOException;
    }

    public static class SseEventBuilderXIUGAIimpl implements SseEventBuilder {
        private final Set<ResponseBodyEmitter.DataWithMediaType> dataToSend = new LinkedHashSet<>(4);
        @Nullable
        private StringBuilder sb;
        @Nullable
        private String id;

        private SseEventBuilderXIUGAIimpl() {
        }

        @Override
        public SseEmitterXIUGAI.SseEventBuilder id(String id) {
            this.id = id;
            return this;
        }

        @Override
        public SseEmitterXIUGAI.SseEventBuilder data(Object object) {
            return this.data(object, (MediaType) null);
        }

        @Override
        public SseEmitterXIUGAI.SseEventBuilder data(Object object, @Nullable MediaType mediaType) {
            this.saveAppendedText();
            if (object instanceof String text) {
                object = StringUtils.replace(text, "\n", "\n");
            }
            this.dataToSend.add(new ResponseBodyEmitter.DataWithMediaType(object, mediaType));
            return this;
        }

        private void saveAppendedText() {
            if (this.sb != null) {
                this.dataToSend.add(new ResponseBodyEmitter.DataWithMediaType(this.sb.toString(), TEXT_PLAIN));
                this.sb = null;
            }
        }

        @Override
        public void send(SseEmitter emitter) throws IOException {
            if (id != null) {
                emitter.send("id:" + id + "\n", TEXT_PLAIN);
            }
            for (ResponseBodyEmitter.DataWithMediaType data : dataToSend) {
                emitter.send(data.getData(), data.getMediaType());
            }
            emitter.send("\n", TEXT_PLAIN);
        }

        public static SseEventBuilderXIUGAIimpl builder() {
            return new SseEventBuilderXIUGAIimpl();
        }
    }
}
