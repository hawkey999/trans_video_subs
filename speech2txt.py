import srt
import time
import datetime
from google.cloud import speech_v1p1beta1 as speech


def long_running_recognize(sample_rate, channels, language_code, storage_uri):
    """
    Transcribe long audio file from Cloud Storage using asynchronous speech
    recognition

    Args:
      storage_uri URI for audio file in GCS, e.g. gs://[BUCKET]/[FILE]
      sample_rate of the audio, e.g. 44100
      channels of audio, e.g. 2
      language_code of audio, e.g. en-US
        # Speech to text language code: https://cloud.google.com/speech-to-text/docs/languages
    """
    start_time = datetime.datetime.now()
    print("Transcribing... {} ".format(storage_uri))
    client = speech.SpeechClient()

    # Encoding of audio data sent, recommended to use loseless codec. Here should match ffmpeg output codec
    encoding = speech.RecognitionConfig.AudioEncoding.FLAC
    # Supported encoding: https://cloud.google.com/speech-to-text/docs/encoding#audio-encodings

    # TODO : Video model now only support en-US
    if language_code == 'en-US':
        config = {
            "enable_word_time_offsets": True,
            "enable_automatic_punctuation": True,
            "sample_rate_hertz": sample_rate,
            "language_code": language_code,
            "encoding": encoding,
            "audio_channel_count": channels,
            "use_enhanced": True,
            "model": "video"
        }
    else:
        config = {
            "enable_word_time_offsets": True,
            "enable_automatic_punctuation": True,
            "sample_rate_hertz": sample_rate,
            "language_code": language_code,
            "encoding": encoding,
            "audio_channel_count": channels,
            "enable_word_confidence": True
        }
    audio = {"uri": storage_uri}

    try:
        operation = client.long_running_recognize(
            request={
                "config": config,
                "audio": audio,
            }
        )
        response = operation.result(timeout=3600)

        subs = []

        for result in response.results:
            # First alternative is the most probable result
            subs = break_sentences(subs, result.alternatives[0])
    except Exception as e:
        print(f"ERROR while transcribing {storage_uri}: ", e)
    spent_time = str(datetime.datetime.now() - start_time)
    print(f"Transcrbed with Time {spent_time}, {storage_uri}")
    return subs


def choose_words(_w):
    """
    Japanese would have hiragana(left) and katakana(right) in the same word for choosing, splitted by "｜"
    日文包括片假名和平假名，识别结果以｜为划分，左边是平假名，右边是对应的片假名，实际上是同一个意思，
    需要从结果中选择｜左边或者右边作为最终结果；逗号区分同一个意思的不同片假名表述；空格划分每个词 / 词组。
    """
    selected_words = ""
    _words_list = _w.split(" ")
    for _word in _words_list:
        if _word.find("|"):
            choices = _word.split("|")
            choose_one = choices[0]
            selected_words += choose_one
        else:
            selected_words += _word+" "
    return selected_words


def break_sentences(subs, alternative, max_chars=40):
    firstword = True
    charcount = 0
    idx = len(subs) + 1
    content = ""
    for w in alternative.words:
        if firstword:
            # first word in sentence, record start time
            start_hhmmss = time.strftime('%H:%M:%S', time.gmtime(
                w.start_time.seconds))
            start_ms = int(w.start_time.microseconds / 1000)
            start = start_hhmmss + "," + str(start_ms)

        if w.word.find("|"):
            wd = w.word.split("|")[0]
        else:
            wd = w.word
        charcount += len(wd)
        content += " " + wd.strip()

        if ("." in wd or "!" in wd or "?" in wd or
                charcount > max_chars or
                ("," in wd and not firstword)):
            # break sentence at: . ! ? or line length exceeded
            # also break if , and not first word
            end_hhmmss = time.strftime('%H:%M:%S', time.gmtime(
                w.end_time.seconds))
            end_ms = int(w.end_time.microseconds / 1000)
            end = end_hhmmss + "," + str(end_ms)
            subs.append(srt.Subtitle(index=idx,
                                     start=srt.srt_timestamp_to_timedelta(start),
                                     end=srt.srt_timestamp_to_timedelta(end),
                                     content=srt.make_legal_content(content)))
            firstword = True
            idx += 1
            content = ""
            charcount = 0
        else:
            firstword = False
    return subs


def write_srt(out_file, language_code, subs):
    srt_file = f"{out_file}.{language_code}.srt"
    print("Writing subtitles to: {}".format(srt_file))
    with open(srt_file, 'w') as f:
        f.writelines(srt.compose(subs))

    return


def write_txt(out_file, language_code, subs):
    txt_file = f"{out_file}.{language_code}.txt"
    print("Writing text to: {}".format(txt_file))
    with open(txt_file, 'w') as f:
        for s in subs:
            f.write(s.content.strip() + "\n")
    return


def speech2txt(sample_rate, channels, language_code, storage_uri, out_file):
    subs = long_running_recognize(sample_rate, channels, language_code, storage_uri)
    write_srt(out_file, language_code, subs)
    write_txt(out_file, language_code, subs)
    return

