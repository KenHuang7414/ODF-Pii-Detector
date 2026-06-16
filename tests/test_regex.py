# tests/test_regex.py
import pytest
from src.regex_detector import detect, validate_tw_id
from src.config import PIIType


class TestValidateTwId:
    def test_valid_ids(self):
        assert validate_tw_id("A123456789") is True
        assert validate_tw_id("A223456781") is True  

    def test_invalid_checksum(self):
        assert validate_tw_id("A123456788") is False
        assert validate_tw_id("B234567890") is False  # 明確測試這個是不合法的

    def test_invalid_format(self):
        assert validate_tw_id("A12345678") is False   # 少一位
        assert validate_tw_id("123456789A") is False  # 格式錯
        assert validate_tw_id("a123456789") is False  # 小寫


class TestDetectIdNumber:
    def test_detects_valid_id(self):
        text = "申請人身分證統一編號 A123456789。"
        matches = detect(text)
        id_matches = [m for m in matches if m.pii_type == PIIType.ID_NUMBER]
        assert len(id_matches) == 1
        assert id_matches[0].text == "A123456789"

    def test_rejects_invalid_checksum(self):
        text = "範例編號 A123456788 僅供參考。"
        matches = detect(text)
        id_matches = [m for m in matches if m.pii_type == PIIType.ID_NUMBER]
        assert len(id_matches) == 0


class TestDetectMobile:
    def test_detects_mobile_with_dash(self):
        text = "手機 0912-345-678。"
        matches = detect(text)
        mobile = [m for m in matches if m.pii_type == PIIType.MOBILE]
        assert len(mobile) == 1
        assert mobile[0].text == "0912-345-678"

    def test_detects_mobile_no_dash(self):
        text = "請致電 0912345678 確認。"
        matches = detect(text)
        mobile = [m for m in matches if m.pii_type == PIIType.MOBILE]
        assert len(mobile) == 1


class TestDetectPhone:
    def test_detects_landline(self):
        text = "聯絡電話 (02)2345-6789。"
        matches = detect(text)
        phone = [m for m in matches if m.pii_type == PIIType.PHONE]
        assert len(phone) == 1


class TestDetectEmail:
    def test_detects_email(self):
        text = "電子郵件 wang.jianguo@example.com。"
        matches = detect(text)
        email = [m for m in matches if m.pii_type == PIIType.EMAIL]
        assert len(email) == 1
        assert email[0].text == "wang.jianguo@example.com"


class TestDetectBirthday:
    def test_detects_western_date_slash(self):
        text = "出生於 1980/07/15。"
        matches = detect(text)
        bday = [m for m in matches if m.pii_type == PIIType.BIRTHDAY]
        assert len(bday) == 1

    def test_detects_western_date_dash(self):
        text = "出生於 1980-07-15。"
        matches = detect(text)
        bday = [m for m in matches if m.pii_type == PIIType.BIRTHDAY]
        assert len(bday) == 1

    def test_detects_western_date_chinese(self):
        text = "出生於 1980年7月15日。"
        matches = detect(text)
        bday = [m for m in matches if m.pii_type == PIIType.BIRTHDAY]
        assert len(bday) == 1

    def test_detects_minguo_arabic(self):
        """民國年＋阿拉伯數字"""
        text = "出生日期民國75年3月20日。"
        matches = detect(text)
        bday = [m for m in matches if m.pii_type == PIIType.BIRTHDAY]
        assert len(bday) == 1

    def test_detects_minguo_chinese_numerals(self):
        """
        民國年＋中文數字，原本是已知限制，升級 pattern 後已支援。
        這個測試從「斷言抓不到」改為「斷言能抓到」，代表解決了一個已知限制。
        """
        text = "出生日期為民國七十五年三月二十日。"
        matches = detect(text)
        bday = [m for m in matches if m.pii_type == PIIType.BIRTHDAY]
        assert len(bday) == 1
        assert "民國七十五年三月二十日" in bday[0].text

    def test_detects_minguo_mixed(self):
        """民國年＋中文數字年份，阿拉伯數字月日（混用）"""
        text = "民國九十一年9月9日出生。"
        matches = detect(text)
        bday = [m for m in matches if m.pii_type == PIIType.BIRTHDAY]
        assert len(bday) == 1

    def test_no_false_positive_year_only(self):
        """只有年沒有月日，不應被抓（交給 LLM 處理）"""
        text = "民國八十年生。"
        matches = detect(text)
        bday = [m for m in matches if m.pii_type == PIIType.BIRTHDAY]
        assert len(bday) == 0

    def test_no_false_positive_nandu(self):
        """民國 XX 年度，不應被誤判為生日"""
        text = "依據教育部113年度科學教育推動計畫辦理。"
        matches = detect(text)
        bday = [m for m in matches if m.pii_type == PIIType.BIRTHDAY]
        assert len(bday) == 0

    def test_no_false_positive_start_year(self):
        """民國 XX 年起實施，不應被誤判"""
        text = "本計畫自民國110年起實施。"
        matches = detect(text)
        bday = [m for m in matches if m.pii_type == PIIType.BIRTHDAY]
        assert len(bday) == 0


class TestDetectAddress:
    def test_detects_full_address(self):
        """完整地址含縣市區路號樓"""
        text = "聯絡地址為台北市中正區重慶南路一段122號5樓。"
        matches = detect(text)
        addr = [m for m in matches if m.pii_type == PIIType.ADDRESS]
        assert len(addr) == 1

    def test_detects_road_number_only(self):
        """只有路名和號，沒有縣市區"""
        text = "住址忠孝東路四段100號。"
        matches = detect(text)
        addr = [m for m in matches if m.pii_type == PIIType.ADDRESS]
        assert len(addr) == 1

    def test_detects_with_lane_alley(self):
        """含巷弄"""
        text = "地址中山北路一段3巷5弄12號2樓。"
        matches = detect(text)
        addr = [m for m in matches if m.pii_type == PIIType.ADDRESS]
        assert len(addr) == 1

    def test_no_false_positive_document_number(self):
        """公文字號含「號」，不應被誤判為地址"""
        text = "發文字號：府教字第1130012345號。"
        matches = detect(text)
        addr = [m for m in matches if m.pii_type == PIIType.ADDRESS]
        assert len(addr) == 0

    def test_no_false_positive_normal_text(self):
        """一般文字不應被誤判"""
        text = "本案經費預算表已檢附於附件，請參閱第三項說明。"
        matches = detect(text)
        addr = [m for m in matches if m.pii_type == PIIType.ADDRESS]
        assert len(addr) == 0


class TestNoFalsePositives:
    def test_normal_text_has_no_matches(self):
        text = "本案經費預算表已檢附於附件，請參閱第三項說明。"
        matches = detect(text)
        assert len(matches) == 0