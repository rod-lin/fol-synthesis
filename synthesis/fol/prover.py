from __future__ import annotations

from typing import Tuple, Optional, Dict, Generator
from enum import Enum
from collections import OrderedDict

import itertools

from .base import *


class QuantifierKind(Enum):
    UNIVERSAL = 0
    EXISTENTIAL = 1

    def dual(self) -> QuantifierKind:
        if self == QuantifierKind.UNIVERSAL:
            return QuantifierKind.EXISTENTIAL
        else:
            return QuantifierKind.UNIVERSAL


QuantifierList = Tuple[Tuple[Variable, QuantifierKind], ...]


class NaturalProof:
    """
    A prover using natural proofs or systematic term instantiation
    """

    @staticmethod
    def get_all_terms(formula: Formula) -> Tuple[Term, ...]:
        """
        Get all terms in a formula
        """
        if isinstance(formula, Falsum) or isinstance(formula, Verum):
            return ()

        elif isinstance(formula, RelationApplication):
            return formula.arguments

        elif isinstance(formula, Equality):
            return (formula.left, formula.right)

        elif isinstance(formula, Conjunction) or \
             isinstance(formula, Disjunction) or \
             isinstance(formula, Implication) or \
             isinstance(formula, Equivalence):
            return NaturalProof.get_all_terms(formula.left) + \
                   NaturalProof.get_all_terms(formula.right)

        elif isinstance(formula, Negation):
            return NaturalProof.get_all_terms(formula.formula)

        elif isinstance(formula, UniversalQuantification) or \
             isinstance(formula, ExistentialQuantification):
            return NaturalProof.get_all_terms(formula.body)

        assert False, f"unsupported formula {formula}"

    @staticmethod
    def get_all_ground_terms_in_term(sort: Sort, term: Term) -> Tuple[Term, ...]:
        """
        Get all ground terms of the given sort in the given term
        """

        # TODO: slow

        if isinstance(term, Variable):
            return ()
        
        elif isinstance(term, Application):
            subterms = sum(map(lambda subterm: NaturalProof.get_all_ground_terms_in_term(sort, subterm), term.arguments), ())

            if term.get_sort() == sort and len(term.get_free_variables()) == 0:
                return (term,) + subterms
            else:
                return subterms

        assert False, f"unsupported term {term}"

    @staticmethod
    def get_all_ground_terms(sort: Sort, formula: Formula) -> Tuple[Term, ...]:
        """
        Get all ground terms of the given sort in the given formula
        """
        return sum(map(
            lambda term: NaturalProof.get_all_ground_terms_in_term(sort, term),
            NaturalProof.get_all_terms(formula),
        ), ())

    @staticmethod
    def flip_quantifier_list(quants: QuantifierList) -> QuantifierList:
        return tuple((var, kind.dual()) for var, kind in quants)

    @staticmethod
    def count_quantifiers(formula: Formula) -> int:
        if isinstance(formula, Falsum) or \
           isinstance(formula, Verum) or \
           isinstance(formula, RelationApplication) or \
           isinstance(formula, Equality):
            return 0

        elif isinstance(formula, Conjunction) or \
             isinstance(formula, Disjunction) or \
             isinstance(formula, Implication) or \
             isinstance(formula, Equivalence):
            return NaturalProof.count_quantifiers(formula.left) + \
                   NaturalProof.count_quantifiers(formula.right)

        elif isinstance(formula, Negation):
            return NaturalProof.count_quantifiers(formula.formula)

        elif isinstance(formula, UniversalQuantification) or \
             isinstance(formula, ExistentialQuantification):
            return NaturalProof.count_quantifiers(formula.body) + 1
        
        assert False, f"unsupported formula {formula}"

    @staticmethod
    def get_longest_variable_name(ast: Union[Term, Formula], default: str = "x") -> str:
        if isinstance(ast, Falsum) or isinstance(ast, Verum):
            return default

        elif isinstance(ast, Variable):
            return ast.name

        elif isinstance(ast, Application) or isinstance(ast, RelationApplication):
            var_name = default

            for argument in ast.arguments:
                name = NaturalProof.get_longest_variable_name(argument)
                if len(name) > len(var_name):
                    var_name = name

            return var_name

        elif isinstance(ast, Equality):
            left_name = NaturalProof.get_longest_variable_name(ast.left)
            right_name = NaturalProof.get_longest_variable_name(ast.right)
            if len(right_name) > len(left_name):
                return right_name
            else:
                return left_name

        elif isinstance(ast, Conjunction) or \
             isinstance(ast, Disjunction) or \
             isinstance(ast, Implication) or \
             isinstance(ast, Equivalence):
            left_name = NaturalProof.get_longest_variable_name(ast.left)
            right_name = NaturalProof.get_longest_variable_name(ast.right)
            if len(left_name) >= len(right_name):
                return left_name
            else:
                return right_name

        elif isinstance(ast, Negation):
            return NaturalProof.get_longest_variable_name(ast.formula)

        elif isinstance(ast, UniversalQuantification) or \
             isinstance(ast, ExistentialQuantification):
            var_name = ast.variable.name
            body_name = NaturalProof.get_longest_variable_name(ast.body)

            if len(var_name) >= len(body_name):
                return var_name
            else:
                return body_name

        elif isinstance(ast, Formula) and ast.is_qfree():
            var_name = default

            for free_var in ast.get_free_variables():
                if len(free_var.name) >= len(var_name):
                    var_name = free_var.name
                
            return var_name

        assert False, f"unsupported ast {ast}"

    @staticmethod
    def prenex_normalize(formula: Formula, var_index: int = 0, var_prefix: Optional[str] = None) -> Tuple[QuantifierList, Formula]:
        """
        Normalize the given formula to its prenex form

        The returned formula will be quantifier-free
        and the quantifiers will be represented by a QuantifierList
        
        All quantified variables will be renamed to <var_prefix><var_index>,
        where <var_prefix> is the longest variable name in the original formula
        All free variables will NOT be renamed

        The quantifier list goes from the outermost (leftmost in the list) to the innermost (rightmost in the list)
        """

        if var_prefix is None:
            # take the longest variable name as prefix to avoid clash
            return NaturalProof.prenex_normalize(formula, var_index, NaturalProof.get_longest_variable_name(formula))

        if isinstance(formula, Falsum) or \
           isinstance(formula, Verum) or \
           isinstance(formula, RelationApplication) or \
           isinstance(formula, Equality):
            return (), formula

        elif isinstance(formula, Conjunction) or \
             isinstance(formula, Disjunction):
            left_quants, left_prenex = NaturalProof.prenex_normalize(formula.left, var_index, var_prefix)
            right_quants, right_prenex = NaturalProof.prenex_normalize(formula.right, var_index + len(left_quants), var_prefix)
            return left_quants + right_quants, type(formula)(left_prenex, right_prenex)

        elif isinstance(formula, Negation):
            quants, prenex = NaturalProof.prenex_normalize(formula.formula, var_index, var_prefix)
            return NaturalProof.flip_quantifier_list(quants), Negation(prenex)

        elif isinstance(formula, Implication):
            left_quants, left_prenex = NaturalProof.prenex_normalize(formula.left, var_index, var_prefix)
            right_quants, right_prenex = NaturalProof.prenex_normalize(formula.right, var_index + len(left_quants), var_prefix)
            return NaturalProof.flip_quantifier_list(left_quants) + right_quants, Implication(left_prenex, right_prenex)

        elif isinstance(formula, Equivalence):
            return NaturalProof.prenex_normalize(
                Conjunction(
                    Implication(formula.left, formula.right),
                    Implication(formula.right, formula.left),
                ),
                var_index,
                var_prefix,
            )

        elif isinstance(formula, UniversalQuantification):
            body_quants, body_prenex = NaturalProof.prenex_normalize(formula.body, var_index + 1, var_prefix)
            renamed_var = Variable(f"{var_prefix}{var_index}", formula.variable.sort)
            return ((renamed_var, QuantifierKind.UNIVERSAL),) + body_quants, body_prenex.substitute({ formula.variable: renamed_var })

        elif isinstance(formula, ExistentialQuantification):
            body_quants, body_prenex = NaturalProof.prenex_normalize(formula.body, var_index + 1, var_prefix)
            renamed_var = Variable(f"{var_prefix}{var_index}", formula.variable.sort)
            return ((renamed_var, QuantifierKind.EXISTENTIAL),) + body_quants, body_prenex.substitute({ formula.variable: renamed_var })

        elif formula.is_qfree():
            return (), formula

        assert False, f"unsupported formula {formula}"

    @staticmethod
    def skolemize(language: Language, formula: Formula) -> Tuple[Language, Formula]:
        """
        Normalize the given formula in prenex form
        then do skolemization for all existentially quantified variables

        The returned formula is the quantifier-free body of the final universal formula

        The language might be expanded to include additional function symbols
        """

        quants, prenex = NaturalProof.prenex_normalize(formula)
        universal_variables = []

        for var, kind in quants:
            if kind == QuantifierKind.UNIVERSAL:
                universal_variables.append(var)
            else:
                # add a skolem function
                fresh_function_name = language.get_fresh_function_name("sk")
                skolem_function_symbol = FunctionSymbol(
                    tuple(universal_var.sort for universal_var in universal_variables),
                    var.sort,
                    fresh_function_name,
                )
                language = language.expand_with_function(skolem_function_symbol)

                # replace occurrences of the variable with an application of the skolem function
                prenex = prenex.substitute({ var: Application(skolem_function_symbol, tuple(universal_variables)) })

        return language, prenex

    @staticmethod
    def term_instantiate(
        language: Language,
        foreground_sort: Sort,
        formulas: Tuple[Formula, ...],
        depth: int,
    ) -> Generator[Formula, None, None]:
        """
        Do term instantiation up to depth <depth> and returns the list of (quantifier free) concrete formulas

        <formulas> should be quantifier free and
        all of their free variables (which should be of the foreground sort) are universally quantified
        """

        assert foreground_sort.smt_hook is None

        ground_terms: Dict[Term, None] = OrderedDict()
        instantiated_formulas: Dict[Formula, None] = OrderedDict()

        # try to find ground terms in the language
        for function_symbol in language.function_symbols:
            if function_symbol.output_sort == foreground_sort and \
            len(function_symbol.input_sorts) == 0:
                ground_terms[Application(function_symbol, ())] = None

        if len(ground_terms) == 0:
            for formula in formulas:
                for ground_term in NaturalProof.get_all_ground_terms(foreground_sort, formula):
                    ground_terms[ground_term] = None

        assert len(ground_terms) != 0, \
               f"the given language does not have a ground term of sort {foreground_sort}"

        assert depth >= 0, f"invalid depth {depth}"

        for _ in range(depth): # TODO: need to align with the depth in the paper
            has_new_formula = False

            # use previous ground terms to instantiate new formulas
            for formula in formulas:
                free_vars = sorted(tuple(var for var in formula.get_free_variables() if var.sort == foreground_sort))

                ordered_ground_terms = tuple(ground_terms.keys())

                for assignment in itertools.product(ordered_ground_terms, repeat=len(free_vars)):
                    substitution = dict(zip(free_vars, assignment))
                    instantiated_formula = formula.substitute(substitution)

                    if instantiated_formula not in instantiated_formulas:
                        instantiated_formulas[instantiated_formula] = None
                        has_new_formula = True

                        # new formula
                        yield instantiated_formula

                    # add new ground terms
                    for ground_term in NaturalProof.get_all_ground_terms(foreground_sort, instantiated_formula):
                        ground_terms[ground_term] = None

            # already converged
            if not has_new_formula:
                break

    @staticmethod
    def encode_validity(theory: Theory, foreground_sort: Sort, goal: Formula, depth: int) -> Tuple[Language, Generator[Formula, None, None]]:
        """
        Reduce the FO-validity of the formula in the given theory (i.e. whether theory |= formula)
        to the unsatisfiability of the returned conjunction of quantifier free, concrete formulas.

        The given goal should be a closed formula

        The possibly expended language is also returned
        """

        language = theory.language

        # collect all sentences in the theory
        # fixpoint definitions are added as equivalence
        normalized_formulas = list(theory.convert_to_fo_theory())

        # skolemize all sentences in the theory
        for i, formula in enumerate(normalized_formulas):
            language, skolemized = NaturalProof.skolemize(language, formula)
            normalized_formulas[i] = skolemized

        # negate the goal formula and then skolemize it
        negated_goal = Negation(goal).quantify_all_free_variables()
        language, skolemized_negated_goal = NaturalProof.skolemize(language, negated_goal)

        normalized_formulas = [skolemized_negated_goal] + normalized_formulas

        # theory |= goal
        # iff theory /\ not goal is unsatisfiable

        return language, NaturalProof.term_instantiate(language, foreground_sort, tuple(normalized_formulas), depth)
