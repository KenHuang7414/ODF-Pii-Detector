# tests/test_regex.py
import pytest
from src.regex_detector import detect, validate_tw_id
from src.config import PIIType


class TestValidateTwId:
    def test_valid_ids(self):
        # 这两个在范本公文里用过，检查码合法
        assert validate_tw_id("A123456789") is True
        assert validate_tw_id("B234567890") is True

    def test_invalid_checksum(self):
        assert validate_tw_id("A123456788") is False

    def test_invalid_format(self):
        assert validate_tw_id("A12345678") is False      # 少一位
        assert validate_tw_id("123456789A") is False     # 格式错
        assert validate_tw_id("a123456789") is False     # 小写


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
    def test_detects_western_date(self):
        text = "出生於 1980/07/15。"
        matches = detect(text)
        bday = [m for m in matches if m.pii_type == PIIType.BIRTHDAY]
        assert len(bday) == 1

    def test_minguo_date_with_chinese_numerals_currently_missed(self):
        """
        這個測試會 FAIL，這是預期的。
        民國七十五年三月二十日 用的是中文數字，目前正則抓不到，
        要靠 llm_detector.py 補。這個測試的存在是為了「記錄」這個已知限制，
        提醒之後不要忘記在 llm_detector 的測試裡補上對應案例。
        """
        text = "出生日期為民國七十五年三月二十日。"
        matches = detect(text)
        bday = [m for m in matches if m.pii_type == PIIType.BIRTHDAY]
        assert len(bday) == 0  # 正則層的已知限制


class TestNoFalsePositives:
    def test_normal_text_has_no_matches(self):
        text = "本案經費預算表已檢附於附件，請參閱第三項說明。"
        matches = detect(text)
        assert len(matches) == 0