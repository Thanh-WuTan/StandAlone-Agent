from typing import List

from requirements.stockpile.base_requirement import BaseRequirement

class Requirement(BaseRequirement):

    def enforce(self, link, operation):
        """
        Given a link and the current operation, check that the operation's knowledge base contains
        at least one fact (and edge) that complies with the requirement.
        :param link
        :param operation
        :return: True if it complies, False if it doesn't
        """
        facts = operation.all_facts()
        filtered_facts = [fact for fact in facts if fact.trait == self.enforcements['source'] and
                                                    link.paw in fact.collected_by]
        if self.enforcements.get('edge', None):
            filtered_facts = [fact for fact in filtered_facts if self._in_relationship_substring(self.enforcements['edge'], fact.relationships)]
        fulfilled = len(filtered_facts) > 0

        return fulfilled

    def _in_relationship_substring(self, key: str, relationships: List[str]):
        return any(key in string for string in relationships)
