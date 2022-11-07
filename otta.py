from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.by import By
from webdriver_manager.firefox import GeckoDriverManager
from dotenv import load_dotenv
from enum import Enum, auto
import traceback
import pathlib
import logging
import json
import sys
import os
import re

FILENAME = os.path.basename(__file__)
AUTO = "--auto" in sys.argv
DEBUG = "--debug" in sys.argv
with open("config.json", "r") as f:
    CONFIG: dict[str, str] = json.load(f)
with open("cover_letter.json") as f:
    COVER_LETTER_DATA: dict[str, object] = json.load(f)

def get_logger():
    logger = logging.getLogger(FILENAME)
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler("otta-automate.log")
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

class InputType(Enum):
    TEXTAREA = auto()
    CHECKBOX = auto()
    DROPDOWN = auto()
    UNKNOWN = auto()

class Sentiment(Enum):
    COVER_LETTER = auto()
    AFFIRM_RIGHT_TO_WORK = auto()
    NEED_SPONSORSHIP = auto()
    HOW_DID_YOU_HEAR = auto()
    PRONOUNS = auto()
    UNKNOWN = auto()

class Question:
    """
    A Question object represents what needs to be entered (Sentiment) and how to enter it (InputType)
    """

    def __init__(self, input_type: InputType, sentiment: Sentiment):
        self.input_type = input_type
        self.sentiment = sentiment

    def __repr__(self):
        return f"(input type: {self.input_type.name}, sentiment: {self.sentiment.name})"

class NoCredentialsException(Exception):
    """
    A custom error to reject execution if the proper env variables aren't set
    """
    def __init__(self):
        super().__init__("You need 'PROFILE_FILE' and 'USER' environment variables set to run this script")

class DriverManager(webdriver.Firefox):
    """
    A wrapper to run the Selenium driver as a context manager and inject our logger
    """
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        try:
            options = FirefoxOptions()
            if (profile := os.getenv("PROFILE_FILE")) and (user := os.getenv("USER")):
                self.logger.info(f"Using profile found for {user}: {profile}")
                pathroot = pathlib.WindowsPath(r"C:\\")
                path = pathroot / "Users" / user / "AppData" / "Local" / "Mozilla" / "Firefox" / "Profiles" / profile
                options.add_argument("--profile")
                options.add_argument(str(path))
            else:
                raise NoCredentialsException()
            super().__init__(service=FirefoxService(GeckoDriverManager().install()), options=options)
            self.implicitly_wait(CONFIG.get("wait") or 30)
            self.logger.info("Driver initialised")
        except Exception as e:
            self.logger.error(f"Crashed on startup with a {repr(e.__class__.__name__)}: view traceback below")
            self.logger.error(traceback.format_exc())
            raise e
    
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        if any(exc):
            # we get the name of an exception with e.__class__.__name__, but exc[0] is not of type Exception
            self.logger.error(f"Script crashed with a {repr(exc[0].__name__)}: view traceback below")
            self.logger.error(traceback.format_exc())
        else:
            self.logger.info("Script ran to completion: exiting")
        self.quit()

    def debug(self, message: str, level=logging.INFO):
        """
        Breakpoint for debug mode
        """
        if DEBUG:
            self.logger.log(level, message)
            breakpoint()

    def find_element_by_data_id(self, id: str):
        """
        Find a SINGLE element using an xpath pattern on the `data-testid` tag
        """
        return self.find_element(By.XPATH, f"//*[@data-testid='{id}']")

    def find_elements_by_data_id(self, id: str):
        """
        Find MULTIPLE elements using an xpath pattern on the `data-testid` tag
        """
        return self.find_elements(By.XPATH, f"//*[@data-testid='{id}']")

    def page_data_text(self, el: str):
        """
        Extract the text from a `data-testid`, or an empty string if it isn't possible
        """
        try:
            return self.find_element_by_data_id(el).text
        except:
            return ""

    def page_data_text_list(self, el: str):
        """
        Extract a list of text from tags with `data-testid` or an empty list if it isn't possible
        """
        try:
            return [i.text for i in self.find_elements_by_data_id(el)]
        except:
            return []

    def get_web_link(self):
        """
        Attempt to get the web link of a company or return None
        """
        try:
            job_card = self.find_element_by_data_id("job-card")
            link = job_card.find_element(By.TAG_NAME, "a")
            return link.get_attribute("href")
        except:
            return None

    def browse_to_application_page(self):
        buttons_panel = self.find_element_by_data_id("desktop-action-panel")
        buttons_panel.find_elements(By.TAG_NAME, "button")[1].click()
        apply_modal = self.find_element_by_data_id("apply-content")
        apply_modal.find_element(By.TAG_NAME, "button").click()

    def extract_input_type(self, text: str):
        try:
            input_instructions = text.split("\n")[-1].lower()
            if "choose an option" in input_instructions:
                return InputType.DROPDOWN
            if "check all" in input_instructions:
                return InputType.CHECKBOX
            if "type your answer" in input_instructions:
                return InputType.TEXTAREA
            self.logger.warning(f"Couldn't identify the input type for a question: {text}")
            return InputType.UNKNOWN
        except IndexError:
            self.logger.warning(f"Couldn't identify the input type for a question: {text}")
            return InputType.UNKNOWN

    def extract_sentiment(self, text: str):
        sentiment = Sentiment.UNKNOWN
        semantic_clues = {
            Sentiment.COVER_LETTER: ["why do you want to work"],
            Sentiment.AFFIRM_RIGHT_TO_WORK: ["right to work in UK", "do have", "do you have", "citizenship", "confirm the right", "confirm you are"],
            Sentiment.NEED_SPONSORSHIP: ["will you need", "sponsor", "sponsorship", "immigration"],
            Sentiment.PRONOUNS: ["preferred name", "pronouns"],
            Sentiment.HOW_DID_YOU_HEAR: ["how did you hear"]
        }
        threshold = 0
        for key, value in semantic_clues.items():
            hits = sum(1 for s in value if s in text.lower())
            if hits > threshold:
                threshold = hits
                sentiment = key
        if threshold == 0:
            self.logger.warning(f"Couldn't identify the sentiment for a question: {text}")
        return sentiment

    def extract_question_info(self, elements: list[WebElement]):
        """
        We want to find out the meaning of the question and the type of input so we can boil it down
        to a `Question` object
        """
        for element in elements:
            yield Question(
                self.extract_input_type(element.text), 
                self.extract_sentiment(element.text)
            )

    def enter_answer(self, element: WebElement, input_type: InputType, answer: str):
        if input_type is InputType.TEXTAREA:
            element.click()
            text_area = element.find_element(By.TAG_NAME, "textarea")
            text_area.send_keys(answer)
            save_btn = element.find_elements(By.TAG_NAME, "button")[1]
            save_btn.click()
        elif input_type is InputType.CHECKBOX:
            pass
        else:
            pass

    def submit_application(self):
        self.find_element_by_data_id("send-application").click()

class JobApplication:
    """
    Used to gather the data and formulate our job application
    """
    def __init__(self, driver: DriverManager):
        try:
            self.company_title = driver.page_data_text("ottas-take").split("Otta's take on ")[-1]
        except IndexError:
            self.company_title = None
        self.job_title = driver.page_data_text("job-title") or None
        self.technologies = driver.page_data_text("job-technology-used").split("\n") or None
        self.office_requirements = driver.page_data_text("office-day-requirements") or None
        self.salary = driver.page_data_text("salary-section").split("k")[0] or None
        self.location_description = driver.page_data_text_list("job-location-tag")
        self.industries = driver.page_data_text_list("company-sector-tag")
        self.benefits = driver.page_data_text_list("company-benefit-bullet")
        self.values = driver.page_data_text_list("company-value-bullet")
        self.job_involves = driver.page_data_text_list("job-involves-bullet")
        self.job_requirements = driver.page_data_text_list("job-requirements-bullet")
        self.web_link = driver.get_web_link()
        if self.minimum_application_requirement():
            driver.logger.info(f"Data gathered for {self.company_title}")

    def minimum_application_requirement(self):
        """
        `bool` -> do we know the title of the job and company? If not, something is wrong or we're on a different page
        """
        return self.company_title is not None and self.job_title is not None

    def replace_templating(self, cover_letter: str):
        """
        Our cover letter data contains some custom templating that we need to convert to the correct values.
        `@x//y#`: this is a reused passage that points to a different piece of text we need to grab.
        `$x`: this is a value that corresponds to a property stored in `JobApplication`.
        """
        template_pointers = re.findall(r"@.+\#", cover_letter)
        for pointer in template_pointers:
            category = pointer.split("//")[0][1:]
            key = pointer.split("//")[1][:-1]
            section = COVER_LETTER_DATA[category][key]
            if section not in cover_letter:
                # if it isn't already in there, add only the first of this section
                cover_letter = cover_letter.replace(pointer, section, 1)
            # we get rid of all the other instances as it'll be the same section duplicated
            cover_letter = cover_letter.replace(pointer, "")
        cover_letter = cover_letter.replace("$company", self.company_title)
        cover_letter = cover_letter.replace("$title", self.job_title)
        if len(days_holiday := [b for b in self.benefits if "days holiday" in b.lower()]) > 0:
            try:
                days = days_holiday[0].split("days holiday")[0].split()[-1]
                cover_letter = cover_letter.replace("$days", int(days))
            except (TypeError, IndexError):
                cover_letter = cover_letter.replace("$days", "the offered amount of")
        return cover_letter

    def append_cover_letter_section(self, name: str, section_list: list[str] | None, includes=False):
        section = ""
        add_base = True
        if section_list is not None:
            if includes:
                included_keys = [k for s in section_list for k in COVER_LETTER_DATA[name].keys() if k in s.lower()]
                for key in included_keys:
                    if add_base:
                        section += "\n" + COVER_LETTER_DATA[name]["base"]
                        add_base = False
                    section += COVER_LETTER_DATA[name][key]
            else:
                for part in section_list:
                    if passage := COVER_LETTER_DATA[name].get(part.lower()):
                        if add_base:
                            section += "\n" + COVER_LETTER_DATA[name]["base"]
                            add_base = False
                        section += passage
        return section

    def create_cover_letter(self):
        """
        Using the information we collected during `__init__`, generate our cover letter
        """
        cover_letter = COVER_LETTER_DATA["intro"]
        for key, value in COVER_LETTER_DATA["title"].items():
            if key in self.job_title:
                cover_letter += value
                break
        cover_letter += self.append_cover_letter_section("technologies", self.technologies)
        cover_letter += self.append_cover_letter_section("skills", self.job_involves)
        cover_letter += self.append_cover_letter_section("industries", self.industries)
        cover_letter += self.append_cover_letter_section("benefits", self.benefits, True)
        for key, value in COVER_LETTER_DATA["work style"].items():
            if (self.office_requirements is not None and key in self.office_requirements) or key in self.location_description:
                cover_letter += "\n" + value
                break
        cover_letter += "\n" + COVER_LETTER_DATA["conclusion"]
        return self.replace_templating(cover_letter)

    def answers(self, questions: list[Question]):
        for question in questions:
            if question.sentiment is Sentiment.COVER_LETTER:
                yield self.create_cover_letter()
            elif question.sentiment is Sentiment.AFFIRM_RIGHT_TO_WORK:
                yield "yes"
            elif question.sentiment is Sentiment.HOW_DID_YOU_HEAR:
                yield "other"
            elif question.sentiment is Sentiment.NEED_SPONSORSHIP:
                yield "no"
            elif question.sentiment is Sentiment.PRONOUNS:
                yield "he/him"
            else:
                yield ""

def main():
    logger = get_logger()
    logger.info(f"Started execution of {FILENAME}")
    logger.info(f"Execution mode: '{'automatic' if AUTO else 'manual'}', debug mode: '{'on' if DEBUG else 'off'}'")
    load_dotenv()

    with DriverManager(logger) as driver:
        driver.get("https://app.otta.com/jobs/theme/apply-via-otta")
        applications_in_session = 0
        while (application := JobApplication(driver)).minimum_application_requirement():
            driver.debug(f"Entering debugger at '{application.company_title}' listing page")
            driver.browse_to_application_page()
            question_elements = driver.find_elements_by_data_id("application-questions-card")
            questions = [question for question in driver.extract_question_info(question_elements)]
            answers = [answer for answer in application.answers(questions)]
            driver.debug(f"Entering debugger at '{application.company_title}' application page")
            for element, question, answer in zip(question_elements, questions, answers):
                driver.enter_answer(element, question.input_type, answer)
            breakpoint()
            applications_in_session += 1
        if applications_in_session > 0:
            logger.info(f"{applications_in_session} job applications made in this session")
        else:
            logger.warning("No job applications made - might be an error or new posts might have been depleted")
            driver.debug("Entering debugger to investigate incident", logging.WARNING)


if __name__ == '__main__':
    main()
