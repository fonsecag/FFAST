import logging


logging.basicConfig(filename = "test.log", encoding = 'utf-8', level = logging.DEBUG)  


logger = logging.getLogger(__name__)


def hello():
    logger.debug("yo??", stack_info=True)


hello()