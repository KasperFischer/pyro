from __future__ import absolute_import, division, print_function

from unittest import TestCase

import pytest
import torch

import pyro
import pyro.infer
from pyro.distributions import Bernoulli, Normal
from tests.common import assert_equal


class HMMSamplingTestCase(TestCase):

    def setUp(self):

        # simple Gaussian-emission HMM
        def model():
            p_latent = pyro.param("p1", torch.tensor([[0.7], [0.3]]))
            p_obs = pyro.param("p2", torch.tensor([[0.9], [0.1]]))

            latents = [torch.ones(1, 1)]
            observes = []
            for t in range(self.model_steps):

                latents.append(
                    pyro.sample("latent_{}".format(str(t)),
                                Bernoulli(torch.index_select(p_latent, 0, latents[-1].view(-1).long()))))

                observes.append(
                    pyro.sample("observe_{}".format(str(t)),
                                Bernoulli(torch.index_select(p_obs, 0, latents[-1].view(-1).long())),
                                obs=self.data[t]))
            return torch.sum(torch.cat(latents))

        self.model_steps = 3
        self.data = [torch.ones(1, 1) for _ in range(self.model_steps)]
        self.model = model


class NormalNormalSamplingTestCase(TestCase):

    def setUp(self):

        pyro.clear_param_store()

        def model():
            loc = pyro.sample("loc", Normal(torch.zeros(1),
                                            torch.ones(1)))
            xd = Normal(loc, torch.ones(1))
            pyro.sample("xs", xd, obs=self.data)
            return loc

        def guide():
            return pyro.sample("loc", Normal(torch.zeros(1),
                                             torch.ones(1)))

        # data
        self.data = torch.zeros(50, 1)
        self.loc_mean = torch.zeros(1)
        self.loc_stddev = torch.sqrt(torch.ones(1) / 51.0)

        # model and guide
        self.model = model
        self.guide = guide


class SearchTest(HMMSamplingTestCase):

    def test_complete(self):
        posterior = pyro.infer.Search(self.model)

        true_latents = set()
        for i1 in range(2):
            for i2 in range(2):
                for i3 in range(2):
                    true_latents.add((float(i1), float(i2), float(i3)))

        tr_latents = set()
        for tr, _ in posterior._traces():
            tr_latents.add(tuple([tr.nodes[name]["value"].view(-1).item()
                                  for name in tr.nodes.keys()
                                  if tr.nodes[name]["type"] == "sample" and
                                  not tr.nodes[name]["is_observed"]]))

        assert true_latents == tr_latents

    def test_marginal(self):
        posterior = pyro.infer.Search(self.model)
        marginal = pyro.infer.Marginal(posterior)
        d, values = marginal._dist_and_values()

        tr_rets = []
        for v in values:
            tr_rets.append(v.view(-1).item())

        assert len(tr_rets) == 4
        for i in range(4):
            assert i + 1 in tr_rets


class ImportanceTest(NormalNormalSamplingTestCase):

    @pytest.mark.init(rng_seed=0)
    def test_importance_guide(self):
        posterior = pyro.infer.Importance(self.model, guide=self.guide, num_samples=5000)
        marginal = pyro.infer.Marginal(posterior)
        posterior_samples = [marginal() for i in range(1000)]
        posterior_mean = torch.mean(torch.cat(posterior_samples))
        posterior_stddev = torch.std(torch.cat(posterior_samples), 0)
        assert_equal(0, torch.norm(posterior_mean - self.loc_mean).item(), prec=0.01)
        assert_equal(0, torch.norm(posterior_stddev - self.loc_stddev).item(), prec=0.1)

    @pytest.mark.init(rng_seed=0)
    @pytest.mark.skip(reason='Slow test - use only for debugging')
    def test_importance_prior(self):
        posterior = pyro.infer.Importance(self.model, guide=None, num_samples=10000)
        marginal = pyro.infer.Marginal(posterior)
        posterior_samples = [marginal() for i in range(1000)]
        posterior_mean = torch.mean(torch.cat(posterior_samples))
        posterior_stddev = torch.std(torch.cat(posterior_samples), 0)
        assert_equal(0, torch.norm(posterior_mean - self.loc_mean).item(), prec=0.01)
        assert_equal(0, torch.norm(posterior_stddev - self.loc_stddev).item(), prec=0.1)
