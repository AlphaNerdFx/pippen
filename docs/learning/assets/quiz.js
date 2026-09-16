// Reusable quiz widget. Immediate, automatic feedback: the tightest loop a
// static page can offer, which is what makes this retrieval practice rather
// than re-reading.
//
// Markup contract:
//
//   <div class="quiz" data-answer="b"
//        data-why-a="Why a is wrong."
//        data-why-b="Why b is right."
//        data-why-c="Why c is wrong.">
//     <p class="q">The question.</p>
//     <div class="quiz-opts">
//       <button value="a">First option</button>
//       <button value="b">Second option</button>
//       <button value="c">Third option</button>
//     </div>
//     <p class="quiz-fb" hidden></p>
//   </div>
//
// Keep option text the same length across a question. A longer or more
// hedged option is a formatting clue, and the learner will read the clue
// instead of recalling the answer.

(function () {
  "use strict";

  function grade(quiz, picked) {
    var answer = quiz.dataset.answer;
    var feedback = quiz.querySelector(".quiz-fb");
    var buttons = quiz.querySelectorAll(".quiz-opts button");

    for (var i = 0; i < buttons.length; i++) {
      var button = buttons[i];
      button.disabled = true;
      if (button.value === answer) {
        button.classList.add("is-right");
      } else if (button.value === picked) {
        button.classList.add("is-wrong");
      }
    }

    var why = quiz.dataset["why" + picked.charAt(0).toUpperCase() + picked.slice(1)];
    var verdict = picked === answer ? "Correct." : "Not that one.";
    feedback.innerHTML = "<strong>" + verdict + "</strong> " + (why || "");
    feedback.hidden = false;
  }

  function wire(quiz) {
    quiz.addEventListener("click", function (event) {
      var button = event.target.closest(".quiz-opts button");
      if (button && !button.disabled) {
        grade(quiz, button.value);
      }
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var quizzes = document.querySelectorAll(".quiz");
    for (var i = 0; i < quizzes.length; i++) {
      wire(quizzes[i]);
    }
  });
})();
