# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from google.genai import types

from app.agent import classify_query, root_agent


def test_classify_shipping_query():
    content = types.Content(role="user", parts=[types.Part.from_text(text="Where is my tracking number SW987654?")])
    event = classify_query(content)
    assert event.actions is not None
    assert event.actions.route == "shipping"


def test_classify_unrelated_query():
    content = types.Content(role="user", parts=[types.Part.from_text(text="What is the recipe for chocolate cake?")])
    event = classify_query(content)
    assert event.actions is not None
    assert event.actions.route == "unrelated"


def test_workflow_structure():
    assert root_agent.name == "customer_support_workflow"
    assert len(root_agent.graph.nodes) >= 3
