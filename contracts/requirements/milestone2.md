# contracts/requirements/milestone2.md

The course's Milestone 2 brief, as given to the group: a requirement contract (A.241), changed only
by a reviewed commit. Plan steps A.225, A.226, A.227 and A.253 are judged against it.

## [MS2] Data Wrangling and Project Redefinition [10/19 - 11/13]

### Key dates

Groups and projects assigned: Monday, October 19

Presentation to your project TF: during the week of November 9, at a time your group arranges with
your TF

Slides, notebook and revised proposal due: Friday, November 13 at 9:59 pm ET (the submission window
closes at 10:00 pm), or at the start of your presentation if it is earlier

Milestone 2 is worth 10% of the overall project grade. Late days cannot be used on project
milestones.

### Objective

In this milestone your group gets the data, loads it, cleans it and learns what it contains, and
then uses what it learned to state the project question precisely. By the end, your group should
have a usable table in a Jupyter notebook and a project question that the data can answer.
Exploratory data analysis and a baseline model come in Milestone 3, so the focus here is the data
itself.

### Deliverables

- An 8 to 10 minute presentation to your project TF, followed by about 10 minutes of questions and
  discussion. Plan for 25 minutes in total.
- The slides from your presentation, as a PDF.
- The Jupyter notebook (.ipynb) that you used to get, load and clean the data.
- A revised proposal of one to two pages, as a PDF. Every group submits one (see below).

One member of the group uploads the slides, the notebook and the revised proposal in a single
submission to the Milestone 2 assignment on Canvas. The submission counts for everyone in your
Canvas project group.

Grading focuses on the quality of your reasoning about the data, not on the visual polish of the
slides. Your answers to your TF's questions are also part of the grade.

### Revised proposal

Every group submits a revised proposal of one to two pages. Your original proposal was written
before your group had the data. Now that your group has loaded, cleaned and examined the data, the
revised proposal updates the plan using what you learned. It should cover:

- The project question: the revised question, and how and why it changed from your original
  proposal. If it did not change, explain what you found in the data that shows the original
  question can be answered.
- The data: the source, with a link, and the number of rows and columns in the table after cleaning.
- What you learned from the data: the findings from this milestone that change your plan, for
  example a large amount of missing data, a small class, or a column you cannot use because of
  information leakage.
- The plan for the rest of the project: the features, models and evaluation your group intends to
  use. Your group makes these design decisions, and the revised proposal should explain them.

Conditionally approved projects must also address the staff conditions. Your project is
conditionally approved if the Status column for your project in the approved project list says
Conditionally approved. Read the Staff conditions and caveats column for your project. Your revised
proposal must take each condition in turn and explain how your group meets it. For example, if a
condition requires the group to keep one question, state the question you kept; if a condition
requires public data, name the source and link to it. Present a summary of how you meet the
conditions in your presentation, because your TF will check each condition with you.

### Presentation

The presentation is on Zoom at a time arranged with your TF. It can be in person if everyone
involved, including your TF, agrees.

Every group member must be present, and each member should present for roughly the same amount of
time.

The presentation can be conversational. It does not need to be scripted.

A suggested structure:

1. The project question and why it is interesting.
2. The data: where it comes from, how you got it, its size, and what one row and each column
   represent.
3. The cleaning and preprocessing you did or plan to do, and why.
4. The revised project question, and how it changed from the original proposal.
5. For conditionally approved projects: how your group meets each condition.
6. Next steps, including which group member does what, and any questions for your TF.

### Notebook

The notebook should begin with your Canvas project group number and the names of the group members.
It should then show, in order:

1. Getting the data: the code that downloads, queries or loads the data from its source. Report the
   total size of the data in megabytes or gigabytes.
2. Understanding the data: what one row represents, what each column represents, the shape of the
   table, the data types, and summary statistics such as the mean, minimum and maximum of each
   numerical column.
3. Cleaning and preprocessing: each step you took, with a short explanation of why. The section
   below lists issues to check.
4. Project question: the revised question, stated so that it is possible to tell at the end of the
   project whether it was answered.

A few clearly labeled plots that help you understand the data (for example, the distribution of the
response variable or the amount of missing data in each column) are useful here. Full exploratory
data analysis is part of Milestone 3.

Your group must already have the data. A project that only has a plan to collect data will not
receive credit for this milestone.

### Issues to check during cleaning and preprocessing

This list is not complete, and not every item applies to every project. If you are unsure whether
one applies to yours, ask your TF.

- Missing data: Measure how much data is missing in each column and look for a pattern, for example
  whether values are missing more often for some groups of observations. Decide how to handle the
  missing values (for example, dropping rows or imputing values) and explain your choice.
- Unusual values: Look for values that are far from the rest of the data or impossible, such as a
  negative age. Decide whether each is an error, which you correct or remove, or a real
  observation, which you keep. Explain the decision.
- Class imbalance: For a classification task, report how many observations are in each class. If
  one class is much smaller than the others, note it now, because it affects which evaluation
  metrics and models make sense in Milestone 3.
- Scale of the features: Report the range of each numerical feature. Features measured on very
  different scales may need to be standardized for models such as regularized regression or
  k-nearest neighbors.
- Information leakage: Check that no column contains information that would not be available at
  the time of the prediction, or that is recorded only after the outcome is known.

### Slide tips

- Check that the text in every plot is large enough to read.
- Label the axes of every plot, and give each plot a title and, if needed, a legend.
- Keep the text on each slide short, because you will say the details aloud.
- Put one main point on each slide.
- Number your slides, so that your TF can refer to a slide by its number during questions.
