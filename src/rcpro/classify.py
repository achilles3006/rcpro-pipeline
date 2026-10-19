"""Classify leads as mandatory under the Act of 9 May 2019: yes, likely, unlikely, unknown.

Rules on activity codes first. LLM step only for unknown leads: it must answer
"unknown" without evidence and list the evidence used. Never send sole traders' names.
"""
